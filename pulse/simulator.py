"""TTI-level multi-cell LTE downlink system simulator."""
from collections import deque

import numpy as np
try:
    from scipy.special import j0
except (ImportError, OSError):
    def j0(x):
        """Bessel function of the first kind order 0 (Taylor series fallback)."""
        s, t, x2_4 = 0.0, 1.0, (float(x) * 0.5) ** 2
        for k in range(1, 15):
            s += t
            t *= -x2_4 / (k * k)
            if abs(t) < 1e-15:
                break
        return s


from .config import SimConfig
from .phy import sinr_to_cqi, cqi_to_eff, bler
from .schedulers import schedule, VOIP, VIDEO, BE

CLASS_NAMES = {VOIP: "voip", VIDEO: "video", BE: "be"}


def hex_sites(n_cells, isd):
    pos = [(0.0, 0.0)]
    for k in range(n_cells - 1):
        a = np.deg2rad(30 + 60 * k)
        pos.append((isd * np.cos(a), isd * np.sin(a)))
    return np.array(pos)


class LTESimulator:
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        # independent streams -> every scheme sees identical users, traffic and fading
        self.rng = np.random.default_rng(cfg.seed)              # topology
        self.rng_traffic = np.random.default_rng(cfg.seed + 1000)
        self.rng_chan = np.random.default_rng(cfg.seed + 2000)
        self.rng_err = np.random.default_rng(cfg.seed + 3000)
        self._build_topology()
        self._build_traffic()
        self._init_state()

    # ------------------------------------------------------------------ setup
    def _build_topology(self):
        c, rng = self.cfg, self.rng
        self.sites = hex_sites(c.n_cells, c.isd_m)
        # Reuse-3 colouring for SFR: centre=0, ring alternates 1/2 so no two neighbours share
        self.color = np.array([0] + [1 + (k % 2) for k in range(c.n_cells - 1)])
        r_cell = c.isd_m / np.sqrt(3)
        pts = []
        for s in self.sites:
            r = np.sqrt(rng.uniform((c.min_dist_m / r_cell) ** 2, 1, c.users_per_cell)) * r_cell
            th = rng.uniform(0, 2 * np.pi, c.users_per_cell)
            pts.append(np.c_[s[0] + r * np.cos(th), s[1] + r * np.sin(th)])
        self.upos = np.vstack(pts)
        self.U = len(self.upos)

        d = np.linalg.norm(self.upos[:, None, :] - self.sites[None, :, :], axis=2)
        d = np.maximum(d, c.min_dist_m)
        pl_db = 128.1 + 37.6 * np.log10(d / 1000.0)            # 3GPP TR 36.814 macro
        shadow = rng.normal(0, c.shadow_std_db, d.shape)
        self.G = 10 ** (-(pl_db + shadow) / 10)                 # linear gain (U, C)
        self.serving = np.argmax(self.G, axis=1)                # strongest-cell association

        self.p_rb = 10 ** (c.tx_power_dbm / 10) / c.n_rb        # mW per PRB
        self.noise = 10 ** ((-174 + 10 * np.log10(c.rb_bw_hz) + c.noise_figure_db) / 10)
        own = self.G[np.arange(self.U), self.serving] * self.p_rb
        intf = (self.G * self.p_rb).sum(1) - own
        self.geometry_db = 10 * np.log10(own / (self.noise + intf))
        self.edge = self.geometry_db < c.edge_geom_db

        # Time-correlated Rayleigh fading per CQI sub-band (Jakes / Clarke AR(1) model)
        fd = c.speed_kmh / 3.6 * c.carrier_hz / 3e8
        self.rho = j0(2 * np.pi * fd * 1e-3)
        self.n_sb = int(np.ceil(c.n_rb / c.subband_size))
        self.h = (rng.normal(size=(self.U, self.n_sb)) + 1j * rng.normal(size=(self.U, self.n_sb))) / np.sqrt(2)
        self.sb_of_rb = np.arange(c.n_rb) // c.subband_size

    def _build_traffic(self):
        c, rng = self.cfg, self.rng
        probs = np.array([c.mix["voip"], c.mix["video"], c.mix["be"]])
        self.cls = rng.choice(3, size=self.U, p=probs / probs.sum())
        self.deadline = np.where(self.cls == VOIP, c.voip_deadline,
                                 np.where(self.cls == VIDEO, c.video_deadline, 10 ** 6))
        self.phase = rng.integers(0, 40, self.U)

    def _init_state(self):
        c = self.cfg
        self.queues = [deque() for _ in range(self.U)]          # [bits_left, arrival_tti]
        self.buffer = np.zeros(self.U)
        self.held = np.zeros(self.U)        # bits of NACKed blocks waiting for the HARQ round trip
        self.harq = deque()                 # (ready_tti, user, bits)
        self.rbar = np.full(self.U, 1.0)
        self.last_served = np.zeros(self.U)
        self.olla = np.zeros(self.U)
        self.hist = np.zeros((c.cqi_delay_tti + 1, self.U, c.n_rb))
        self.tx_hist = np.zeros((c.cqi_delay_tti + 1, c.n_cells, c.n_rb))
        self.pmask = np.ones((c.n_cells, c.n_rb))
        self.edge_rb = np.zeros((c.n_cells, c.n_rb), dtype=bool)
        ne = c.n_rb // 3
        for k in range(c.n_cells):
            self.edge_rb[k, self.color[k] * ne:(self.color[k] + 1) * ne] = True
        self.sfr_ratio = np.ones(c.n_cells)

        # statistics
        self.served_bits = np.zeros(self.U)
        self.arrived_bits = np.zeros(self.U)
        self.dropped_bits = np.zeros(self.U)
        self.delays = {VOIP: [], VIDEO: [], BE: []}
        self.tb_tx = 0
        self.tb_err = 0
        self.energy_j = np.zeros(c.n_cells)
        self.sleep_tti = np.zeros(c.n_cells)
        self.rb_used = 0

    # --------------------------------------------------------------- per-TTI
    def _arrivals(self, t):
        c, rng = self.cfg, self.rng_traffic
        for u in range(self.U):
            k, bits = self.cls[u], 0.0
            if k == VOIP and (t + self.phase[u]) % c.voip_period == 0:
                bits = c.voip_bits
            elif k == VIDEO and (t + self.phase[u]) % c.video_period == 0:
                mean = c.video_rate_bps * c.video_period / 1000 * c.load_scale
                bits = rng.lognormal(np.log(mean) - 0.125, 0.5)
            elif k == BE:
                lam = c.be_rate_bps * c.load_scale / c.be_file_bits / 1000
                if rng.random() < lam:
                    bits = rng.exponential(c.be_file_bits)
            if bits > 0:
                self.queues[u].append([bits, t])
                self.buffer[u] += bits
                self.arrived_bits[u] += bits

    def _drop_expired(self, t):
        for u in np.where(self.cls != BE)[0]:
            q = self.queues[u]
            while q and t - q[0][1] > self.deadline[u]:
                self.dropped_bits[u] += q[0][0]
                self.buffer[u] -= q[0][0]
                q.popleft()

    def _hol(self, t):
        return np.array([t - q[0][1] if q else 0 for q in self.queues])

    def _sinr(self, active):
        """Actual SINR (U, RB) given which PRBs each cell transmits on this TTI."""
        c = self.cfg
        tx = active * self.pmask * self.p_rb                     # (C, RB) transmitted mW
        rx_all = self.G @ tx                                      # (U, RB) received from all cells
        own_tx = self.pmask[self.serving] * self.p_rb             # serving-cell power if scheduled
        own_gain = self.G[np.arange(self.U), self.serving][:, None]
        fade = np.abs(self.h[:, self.sb_of_rb]) ** 2
        signal = own_tx * own_gain * fade
        intf = rx_all - own_gain * tx[self.serving]
        return 10 * np.log10(signal / (self.noise + np.maximum(intf, 0)))

    def _update_sfr(self):
        c = self.cfg
        ne = c.n_rb // 3
        for k in range(c.n_cells):
            users = np.where(self.serving == k)[0]
            demand = self.buffer[users] + self.rbar[users]
            share = demand[self.edge[users]].sum() / max(demand.sum(), 1e-9)
            ratio = np.clip(1 + (c.sfr_max_ratio - 1) * share / 0.5, 1, c.sfr_max_ratio)
            self.sfr_ratio[k] = ratio
            lo = c.n_rb / (ne * ratio + c.n_rb - ne)              # keeps total power constant
            self.pmask[k] = np.where(self.edge_rb[k], ratio * lo, lo)

    def step(self, t):
        c, rng = self.cfg, self.rng_err
        self._arrivals(t)
        self._drop_expired(t)
        if c.sfr and t % c.sfr_update_tti == 0:
            self._update_sfr()

        while self.harq and self.harq[0][0] <= t:      # HARQ RTT elapsed -> retransmission allowed
            _, u, b = self.harq.popleft()
            self.held[u] = max(self.held[u] - b, 0.0)
        eligible = np.maximum(self.buffer - self.held, 0.0)

        reported = self.hist[(t - c.cqi_delay_tti) % len(self.hist)] if t >= c.cqi_delay_tti \
            else self.hist[0]
        rep_off = reported + (self.olla[:, None] if c.olla else 0.0)
        cqi_rep = sinr_to_cqi(rep_off)
        if c.olla:   # the offset may lower the MCS but never push an in-range user out of range
            cqi_rep = np.where(sinr_to_cqi(reported) > 0, np.maximum(cqi_rep, 1), 0)
        est_rate = cqi_to_eff(cqi_rep) * c.re_bits_per_rb

        hol = self._hol(t)
        ctx = dict(buffer=eligible, rbar=self.rbar, hol=hol, cls=self.cls,
                   deadline=self.deadline, last_served=self.last_served, t=t, edge=self.edge)
        alloc = -np.ones((c.n_cells, c.n_rb), dtype=int)
        for k in range(c.n_cells):
            users = np.where(self.serving == k)[0]
            ctx["edge_rb_mask"] = self.edge_rb[k]
            alloc[k] = schedule(c, ctx, users, est_rate[users])

        active = (alloc >= 0).astype(float)
        sinr = self._sinr(active)
        tx_now = active * self.pmask * self.p_rb
        if t == 0:
            self.hist[:] = sinr
            self.tx_hist[:] = tx_now
        tx_then = self.tx_hist[(t - c.cqi_delay_tti) % len(self.hist)]
        self.hist[t % len(self.hist)] = sinr
        self.tx_hist[t % len(self.hist)] = tx_now

        # Link adaptation input. ICA (interference-coordinated LA): the central controller knows
        # which PRBs every cell transmits on *now* and on the TTI the CQI was measured. Using
        # neighbour RSRP (already reported for handover) it removes the interference that existed
        # then and adds the interference that exists now -> fixes the "flashlight" mismatch.
        la_db = reported
        if c.ica:
            own_g = self.G[np.arange(self.U), self.serving][:, None]
            i_then = np.maximum(self.G @ tx_then - own_g * tx_then[self.serving], 0)
            i_now = np.maximum(self.G @ tx_now - own_g * tx_now[self.serving], 0)
            la_db = reported + 10 * np.log10((self.noise + i_then) / (self.noise + i_now))
        if c.olla:
            la_db = la_db + self.olla[:, None]

        served = np.zeros(self.U)
        for k in range(c.n_cells):
            used = alloc[k] >= 0
            if used.any():
                self.energy_j[k] += (c.p0_w + c.delta_p * c.pmax_w *
                                     (self.pmask[k][used].sum() / c.n_rb)) * 1e-3
                self.rb_used += used.sum()
            else:
                self.energy_j[k] += (c.psleep_w if c.energy else c.p0_w) * 1e-3
                self.sleep_tti[k] += 1
            for u in np.unique(alloc[k][used]):
                rbs = np.where(alloc[k] == u)[0]
                cqi = int(sinr_to_cqi(la_db[u, rbs].mean()))
                if cqi == 0:
                    cqi = 1                              # scheduled users get at least MCS of CQI 1
                tb = min(len(rbs) * cqi_to_eff(cqi) * c.re_bits_per_rb, eligible[u])
                self.tb_tx += 1
                ok = rng.random() > bler(sinr[u, rbs].mean(), cqi)
                if c.olla:
                    step_up = c.olla_step_down * c.olla_target_bler / (1 - c.olla_target_bler)
                    self.olla[u] = np.clip(self.olla[u] + (step_up if ok else -c.olla_step_down), -6, 3)
                self.last_served[u] = t
                if not ok:
                    self.tb_err += 1                     # HARQ: retransmit after 8 ms RTT
                    self.held[u] += tb
                    self.harq.append((t + c.harq_rtt, u, tb))
                    continue
                served[u] = tb
                self._dequeue(u, tb, t)

        self.served_bits += served
        self.rbar = (1 - 1 / c.pf_tc) * self.rbar + served / c.pf_tc
        # fading evolution
        rc = self.rng_chan
        w = (rc.normal(size=self.h.shape) + 1j * rc.normal(size=self.h.shape)) / np.sqrt(2)
        self.h = self.rho * self.h + np.sqrt(1 - self.rho ** 2) * w
        return alloc, sinr

    def _dequeue(self, u, bits, t):
        q = self.queues[u]
        self.buffer[u] = max(self.buffer[u] - bits, 0.0)
        while bits > 1e-9 and q:
            if q[0][0] <= bits + 1e-9:
                bits -= q[0][0]
                self.delays[self.cls[u]].append(t - q[0][1] + 1)
                q.popleft()
            else:
                q[0][0] -= bits
                bits = 0

    # ------------------------------------------------------------------- run
    def run(self):
        for t in range(self.cfg.n_tti):
            self.step(t)
        return self.metrics()

    def metrics(self):
        c = self.cfg
        T = c.n_tti / 1000.0
        thr = self.served_bits / T
        cell_tput = self.served_bits.sum() / T / c.n_cells
        out = {"scheme": c.label, "load": c.load_scale, "seed": c.seed,
               "cell_tput_mbps": cell_tput / 1e6,
               "spectral_eff": cell_tput / (c.n_rb * c.rb_bw_hz),
               "bler": self.tb_err / max(self.tb_tx, 1),
               "rb_util": self.rb_used / (c.n_tti * c.n_cells * c.n_rb),
               "energy_kj": self.energy_j.sum() / 1000,
               "avg_power_w": self.energy_j.sum() / T / c.n_cells,
               "bits_per_joule": self.served_bits.sum() / self.energy_j.sum(),
               "sleep_ratio": self.sleep_tti.sum() / (c.n_tti * c.n_cells)}
        be = self.cls == BE
        # User satisfaction = served / offered bits; comparable across light and heavy users
        has = self.arrived_bits > 0
        sat = self.served_bits[has] / self.arrived_bits[has]
        out["jain_fairness"] = sat.sum() ** 2 / (len(sat) * (sat ** 2).sum())
        out["sat_p5"] = np.percentile(sat, 5)
        e = self.edge[has]
        out["edge_satisfaction"] = sat[e].mean() if e.any() else np.nan
        out["be_goodput_ratio"] = self.served_bits[be].sum() / max(self.arrived_bits[be].sum(), 1)
        for k, name in CLASS_NAMES.items():
            m = self.cls == k
            if len(self.delays[k]) > 0:
                d = np.array(self.delays[k])
                out[f"{name}_delay_ms"] = float(np.mean(d))
                out[f"{name}_delay_p95_ms"] = float(np.percentile(d, 95))
            else:
                out[f"{name}_delay_ms"] = 0.0
                out[f"{name}_delay_p95_ms"] = 0.0
            out[f"{name}_plr"] = float(self.dropped_bits[m].sum() / max(self.arrived_bits[m].sum(), 1))
        rt = self.cls != BE
        plr_u = self.dropped_bits / np.maximum(self.arrived_bits, 1)
        limit = np.where(self.cls == VOIP, 0.01, 0.02)
        out["qos_satisfied_pct"] = 100 * (plr_u[rt] <= limit[rt]).mean()
        return out
