# -*- coding: utf-8 -*-
"""
LiF Hugoniot 数据修复（LASL SHD p.296-297）

背景：
  materials/lasl_shd/lithium_fluoride_single_crystal_loo_p296_lasl.txt
  由 ref/shd.pdf OCR 导入时出错：rho0 误为 0.5785（真值 2.638），
  48 行中大量为 OCR 坏行/伪造行。本脚本从 ref/shd_md/p312.md + p313.md
  的 OCR 原始数字重建权威表。

方法：
  原书左栏四列 (rho0, Us, Up, P[GPa])。OCR 系统性把 6 认成 8
  （如 2.839→2.639、8.902→6.902）。对每个字段枚举数位修复候选
  （8→6 / 6→8 替换、相邻转位），用三重自洽打分取最优：
    1) Rankine-Hugoniot:  P = rho0 * Us * Up   (g/cm3·(km/s)^2 = GPa)
    2) 原书页内拟合:      Us = 5.15 + 1.35 * Up
    3) 右栏比容 V(cm3/g): Us_V = Up * rho / (rho - rho0), rho = 1/V
       （V 栏同样允许 8→6 修复；打印对齐供人工复核，不参与选优）

用法：
  python scripts/repair_lif_hugoniot.py            # 只打印分析，不写文件
  python scripts/repair_lif_hugoniot.py --write    # 人工复核后写入修复文件
"""
import itertools
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # IM_tool 根目录
OUT_FILE = BASE / "im_app" / "standard_library" / "materials" / "lasl_shd" \
    / "lithium_fluoride_single_crystal_loo_p296_lasl.txt"
META_FILE = BASE / "im_app" / "standard_library" / "metadata.json"

# ---- OCR 原始行（p312 = 书 p.296，21 行；p313 = 书 p.297，2 行）----
OCR_ROWS = [
    # (rho0, Us, Up, P_GPa)
    ("2.640", "5.797", ".451", "8.902"),
    ("2.640", "5.606", ".509", "7.605"),
    ("2.839", "8.061", ".631", "10.093"),
    ("2.640", "8.018", ".872", "10.873"),
    ("2.839", "8.432", ".943", "18.007"),
    ("2.842", "8.354", ".945", "15.884"),
    ("2.841", "8.769", "1.224", "21.946"),
    ("2.836", "8.621", "1.238", "22.259"),
    ("2.833", "7.509", "1.896", "33.532"),
    ("2.641", "7.459", "1.734", "34.156"),
    ("2.839", "7.749", "1.924", "39.345"),
    ("2.837", "8.164", "2.229", "48.105"),
    ("2.640", "8.570", "2.508", "56.743"),
    ("2.641", "9.002", "2.815", "68.925"),
    ("2.837", "9.123", "2.981", "71.715"),
    ("2.641", "9.604", "3.197", "81.089"),
    ("2.846", "9.566", "3.263", "82.785"),
    ("2.814", "9.639", "3.410", "85.920"),
    ("2.835", "9.923", "3.477", "90.913"),
    ("2.635", "9.952", "3.572", "93.870"),
    ("2.642", "9.929", "3.621", "94.966"),
    # p313（书 p.297）
    ("2.641", "10.397", "3.801", "104.370"),
    ("2.636", "10.407", "3.931", "107.839"),
]

# 右栏 V(cm3/g)，按左栏行序；第 9 行原 OCR 乱码 ".2!?40"，还原为 .2940
# （经 R-H 闭合验证：2.633×7.509/(7.509-1.696) → V=0.2942 ✓）
# 第 13/14 行（idx 12/13）V 栏乱序（.2879/.2802 破坏单调性），不参与校验
OCR_V = [
    ".3493", ".3458", ".3395", ".3365", ".3234", ".3222", ".3104", ".3105",
    ".2940",  # 乱码 "2!?40" 的人工还原
    ".2906", ".2848", ".2759", None, None, ".2553", ".2526", ".2493",
    ".2472", ".2465", ".2433", ".2405",
    None, None,  # p313 两行无 V 栏
]

FIT_C0, FIT_S = 5.15, 1.35  # 原书页内给出的线性拟合
RH_TOL = 0.0015             # R-H 闭合硬阈值（书内 P 列自算，应闭合 <0.15%）


def variants(tok: str):
    """返回候选 (字符串, 代价)：8↔6 数位替换=1（本扫描的系统误差），
    相邻转位=3（其他行中零实例，仅兜底）。"""
    out = {tok: 0}
    positions8 = [i for i, c in enumerate(tok) if c == "8"]
    positions6 = [i for i, c in enumerate(tok) if c == "6"]
    flips = positions8 + positions6
    for i in flips:
        c = tok[i]
        r = "6" if c == "8" else "8"
        out[tok[:i] + r + tok[i + 1:]] = 1
    for i, j in itertools.combinations(flips, 2):
        t = list(tok)
        for k in (i, j):
            t[k] = "6" if t[k] == "8" else "8"
        out["".join(t)] = 2
    for i in range(len(tok) - 1):
        if tok[i] != tok[i + 1] and tok[i] not in ".-" and tok[i + 1] not in ".-":
            out.setdefault(tok[:i] + tok[i + 1] + tok[i] + tok[i + 2:], 3)
    return out.items()


def repair():
    results = []
    for idx, (r0, us, up, p) in enumerate(OCR_ROWS):
        alts = []
        for (c0, w0), (cus, wus), (cup, wup), (cp, wp) in itertools.product(
            variants(r0), variants(us), variants(up), variants(p)
        ):
            try:
                rho0, usv, upv, pv = float(c0), float(cus), float(cup), float(cp)
            except ValueError:
                continue
            # 物理合理性窗口
            if not (2.60 <= rho0 <= 2.68 and 4.0 <= usv <= 12.0 and 0.2 <= upv <= 4.5):
                continue
            if not (0.1 <= pv <= 120.0):
                continue
            r_p = abs(pv - rho0 * usv * upv) / pv
            if r_p > RH_TOL:  # 书内 P 列由 rho0*Us*Up 自算，必须闭合
                continue
            r_fit = abs(usv - (FIT_C0 + FIT_S * upv)) / usv
            r_v = float("inf")
            if OCR_V[idx] is not None:
                rho = 1.0 / float(OCR_V[idx])
                if rho > rho0:
                    us_v = upv * rho / (rho - rho0)
                    r_v = abs(us_v - usv) / usv
            alts.append(dict(rho0=rho0, us=usv, up=upv, p=pv, r_p=r_p,
                             r_fit=r_fit, r_v=r_v, units=w0 + wus + wup + wp,
                             score=10 * (w0 + wus + wup + wp) + 2 * r_p
                                   + 0.25 * r_fit + 0.5 * min(r_v, 1.0),
                             changed=[t for t, o in ((c0, r0), (cus, us), (cup, up), (cp, p)) if t != o]))
        alts.sort(key=lambda x: x["score"])
        results.append((idx, alts[:3]))
    return results


def main():
    rows = repair()
    print(f"{'i':>2} {'rho0':>6} {'Us':>7} {'Up':>6} {'P(GPa)':>8} {'r_P%':>6} "
          f"{'rfit%':>6} {'rV%':>6} {'u':>2}  changed")
    clean = []
    for idx, alts in rows:
        if not alts:
            print(f"{idx:>2}  --- 无法修复，需人工 ---")
            continue
        b = alts[0]
        rv = f"{100 * b['r_v']:6.2f}" if b["r_v"] != float("inf") else "   -- "
        print(f"{idx:>2} {b['rho0']:>6.3f} {b['us']:>7.3f} {b['up']:>6.3f} "
              f"{b['p']:>8.3f} {100 * b['r_p']:>6.2f} {100 * b['r_fit']:>6.2f} "
              f"{rv} {b['units']:>2}  "
              f"{','.join(b['changed']) if b['changed'] else '-'}")
        clean.append(b)

    import numpy as np
    up = np.array([c["up"] for c in clean])
    us = np.array([c["us"] for c in clean])
    n = len(up)
    A = np.vstack([np.ones(n), up]).T
    cov = np.linalg.inv(A.T @ A)
    a, b_ = cov @ (A.T @ us)
    resid = us - (a + b_ * up)
    s2 = float(resid @ resid) / (n - 2)
    se_a = float(np.sqrt(s2 * cov[0, 0]))
    se_b = float(np.sqrt(s2 * cov[1, 1]))
    print(f"\nLSQ of cleaned rows: Us = {a:.3f}({se_a:.3f}) + {b_:.3f}({se_b:.3f})*Up"
          f"   RMS resid = {float(np.sqrt(resid @ resid / n)):.3f} km/s")
    print(f"Book fit on page:   Us = {FIT_C0} + {FIT_S}*Up")
    print(f"rows: {len(clean)}")

    if "--write" in sys.argv:
        write_file(clean, se_a, se_b)
    else:
        print("\n[dry-run] 未写入。人工复核后加 --write 执行。")


def write_file(clean, se_a, se_b):
    import numpy as np
    up = np.array([c["up"] for c in clean])
    us = np.array([c["us"] for c in clean])
    rho0_arr = np.array([c["rho0"] for c in clean])
    p_gpa = np.array([c["p"] for c in clean])
    rho = rho0_arr * us / (us - up)
    comp = us / (us - up)

    lines = []
    lines.append("# " + "=" * 77)
    lines.append("# Hugoniot Data File")
    lines.append("# Format Version: 1.0")
    lines.append("# " + "=" * 77)
    lines.append("# Material:          LITHIUM FLUORIDE, single-crystal, [100]")
    lines.append("# Reference:         LASL Shock Hugoniot Data (Marsh, 1980), p.296-297, Ref.37")
    lines.append("# Initial Density:   2.638 g/cm^3")
    # Error 元数据须在前 15 行内（_read_header_lines 只读 15 行）
    lines.append("# Error Model: linear")
    lines.append("# Error Formula: Us = a0 + a1*(up - beta)")
    lines.append("# Error Params: a0=5.15 a1=1.35 beta=0 "
                 f"sigma_a0={se_a:.3f} sigma_a1={se_b:.3f}")
    lines.append("# Data Source:       ref/shd.pdf book p.296-297 (pdf p.312-313); "
                 "rebuilt by scripts/repair_lif_hugoniot.py")
    lines.append("# Date Created:      2026-08-27 (repaired 2026-10-15)")
    lines.append("# Notes: Experimental Hugoniot, 23 shots, per-shot rho0 2.614-2.646 g/cm^3. "
                 "Book linear fit on page: Us = 5.15 + 1.35*Up (km/s);"
                 " LSQ of these 23 rows gives Us = 5.150(0.029) + 1.352(0.012)*Up.")
    lines.append("#       2026-10-15 repair: fixed wrong header rho0 (was 0.5785); "
                 "dropped 25 fabricated/garbled rows of the 2026-08-27 OCR import")
    lines.append("#       (import had misread V/V0 column as rho and invented Up 4-5 km/s rows);")
    lines.append("#       systematic OCR 6->8 digit errors repaired per-row via Rankine-Hugoniot "
                 "closure P=rho0*Us*Up (all 23 rows close <=0.15%) plus specific-volume "
                 "column cross-check (Us from V agrees <=0.7%, typically <0.1%).")
    lines.append("#       Error Params sigma values are LSQ standard errors of the 23 cleaned rows.")
    lines.append("# " + "=" * 77)
    lines.append("# Column Units:")
    lines.append("#   Up      km/s       - Particle velocity")
    lines.append("#   Us      km/s       - Shock velocity")
    lines.append("#   P       Mbar       - Pressure (1 Mbar = 100 GPa)")
    lines.append("#   rho     g/cm^3     - Density")
    lines.append("#   eta     -          - Compression ratio (rho/rho0)")
    lines.append("#   T       eV         - Temperature (optional)")
    lines.append("#   E       MJ/g       - Internal energy (optional)")
    lines.append("# " + "=" * 77)
    lines.append("Up(km/s)\tUs(km/s)\tP(Mbar)\trho(g/cm3)\tcompression\tT(eV)\tE(MJ/g)\tsource")
    for i in range(len(up)):
        lines.append(
            f"{up[i]:.3f}\t{us[i]:.3f}\t{p_gpa[i] / 100.0:.5f}\t{rho[i]:.3f}\t"
            f"{comp[i]:.5f}\t\t\tLASL_p296"
        )
    lines.append("# " + "=" * 77)
    lines.append("# End of Data")
    lines.append(f"# Total Points: {len(up)}")
    lines.append(f"# Up Range: [{up.min():.3f}, {up.max():.3f}] km/s")
    lines.append(f"# P Range: [{p_gpa.min() / 100:.5f}, {p_gpa.max() / 100:.5f}] Mbar")
    lines.append(f"# Compression Range: [{comp.min():.4f}, {comp.max():.4f}]")
    lines.append("# " + "=" * 77)

    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"written: {OUT_FILE}")

    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    hit = False
    for m in meta.get("materials", []):
        if m.get("id") == "lithium_fluoride_single_crystal_loo_p296_lasl":
            m["rho0"] = 2.638
            m["name"] = "LITHIUM FLUORIDE, single-crystal, [100]"
            m["points"] = int(len(up))
            m["up_range"] = [round(float(up.min()), 3), round(float(up.max()), 3)]
            m["p_range"] = [round(float(p_gpa.min() / 100), 5), round(float(p_gpa.max() / 100), 5)]
            m["compression_range"] = [round(float(comp.min()), 5), round(float(comp.max()), 5)]
            hit = True
    if hit:
        META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        print("metadata.json updated (rho0=2.638, name [100])")
    else:
        print("WARNING: metadata entry not found!")


if __name__ == "__main__":
    main()
