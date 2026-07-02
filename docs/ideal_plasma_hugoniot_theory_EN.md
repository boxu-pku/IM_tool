# Ideal Plasma Hugoniot — Theoretical Derivation

## 1. Background

In shock wave impedance matching analysis, low-density foam materials (such as CH foam) under strong shock loading are typically in a fully ionized state, and their equation of state can be approximated by the **ideal gas (γ-law) model**. Unlike solid Hugoniots that require table lookup or empirical fitting, the Hugoniot of an ideal plasma has an analytic form that can be fully described with only two parameters: the initial density $\rho_0$ and the adiabatic index $\gamma$.

---

## 2. Rankine-Hugoniot Jump Relations (General Form)

For a normal shock wave, the conservation equations yield three jump conditions:

| Conservation Law | Equation |
|--------|------|
| Mass | $\rho_0 U_s = \rho (U_s - U_p)$ |
| Momentum | $P - P_0 = \rho_0 U_s U_p$ |
| Energy | $E - E_0 = \dfrac{P + P_0}{2}\left(\dfrac{1}{\rho_0} - \dfrac{1}{\rho}\right)$ |

where:
- $\rho_0$ — initial density (g/cm³)
- $\rho$ — post-shock density (g/cm³)
- $U_s$ — shock wave velocity (km/s)
- $U_p$ — particle velocity (km/s)
- $P$ — pressure (Mbar)
- $P_0$ — initial pressure
- $E$ — specific internal energy (MJ/g)

---

## 3. Ideal Gas (γ-law) Equation of State

The thermal equation of state for an ideal gas is:

$$P = (\gamma - 1) \rho e$$

where $e$ is the specific internal energy (internal energy per unit mass), and $\gamma$ is the adiabatic index (specific heat ratio $C_p / C_v$).

For a **monatomic ideal gas / fully ionized plasma**, only translational degrees of freedom (3) exist, hence:

$$\gamma = \frac{f + 2}{f} = \frac{5}{3} \approx 1.667$$

---

## 4. Hugoniot Derivation in the Strong Shock Limit

### 4.1 Basic Assumptions

For a **strong shock** ($P \gg P_0$), the following approximations are made:

1. **$P_0 \approx 0$**: the initial pressure is negligible compared to the post-shock pressure
2. **$E_0 \approx 0$**: the initial specific internal energy is negligible compared to the post-shock value
3. **The material obeys the γ-law EOS**: $P = (\gamma - 1)\rho e$

### 4.2 Derivation: Compression Ratio $\rho / \rho_0$

From the energy equation, in the strong shock limit:

$$E = \frac{P}{2}\left(\frac{1}{\rho_0} - \frac{1}{\rho}\right) = \frac{P(\rho - \rho_0)}{2\rho\rho_0}$$

Substituting the γ-law equation of state $E = e = \dfrac{P}{(\gamma - 1)\rho}$:

$$\frac{P}{(\gamma - 1)\rho} = \frac{P(\rho - \rho_0)}{2\rho\rho_0}$$

Eliminating $P$ and $\rho$:

$$\frac{1}{\gamma - 1} = \frac{\rho - \rho_0}{2\rho_0}$$

$$2\rho_0 = (\gamma - 1)(\rho - \rho_0)$$

$$2\rho_0 + (\gamma - 1)\rho_0 = (\gamma - 1)\rho$$

$$\rho_0(\gamma + 1) = (\gamma - 1)\rho$$

$$\boxed{\frac{\rho}{\rho_0} = \frac{\gamma + 1}{\gamma - 1}}$$

For $\gamma = 5/3$:

$$\frac{\rho}{\rho_0} = \frac{5/3 + 1}{5/3 - 1} = \frac{8/3}{2/3} = 4$$

That is, **in the strong shock limit, the compression ratio is a constant 4, independent of shock strength**. This is an important characteristic of γ-law gases.

### 4.3 Derivation: $U_s$-$U_p$ Relation

From the mass conservation equation:

$$\rho_0 U_s = \rho(U_s - U_p)$$

$$U_s = \frac{\rho U_p}{\rho - \rho_0} = \frac{(\rho/\rho_0) U_p}{(\rho/\rho_0) - 1}$$

Substituting the strong-shock-limit compression ratio $\rho/\rho_0 = (\gamma+1)/(\gamma-1)$:

$$U_s = \frac{(\gamma+1)/(\gamma-1)}{(\gamma+1)/(\gamma-1) - 1} \cdot U_p = \frac{(\gamma+1)/(\gamma-1)}{2/(\gamma-1)} \cdot U_p$$

$$\boxed{U_s = \frac{\gamma + 1}{2} U_p}$$

For $\gamma = 5/3$: $U_s = \frac{4}{3} U_p$

**Note**: The $U_s$-$U_p$ relation is **linear**, with slope $(\gamma+1)/2$. This is formally similar to the linear $U_s$-$U_p$ relation for solid materials ($U_s = C_0 + s \cdot U_p$), but the ideal gas intercept is $C_0 = 0$.

### 4.4 Derivation: $P$-$U_p$ Relation (Hugoniot Curve)

From the momentum equation, in the strong shock limit:

$$P = \rho_0 U_s U_p$$

Substituting $U_s = \frac{\gamma+1}{2} U_p$:

$$P = \rho_0 \cdot \frac{\gamma + 1}{2} \cdot U_p^2$$

**Unit conversion**: $\rho_0$ is in g/cm³, $U_s$ and $U_p$ are in km/s.

$$P \text{ [Mbar]} = \rho_0 \text{ [g/cm}^3\text{]} \times U_s \text{ [km/s]} \times U_p \text{ [km/s]} \times 0.01$$

where the factor 0.01 arises from:

$$1 \text{ Mbar} = 10^{12} \text{ dyn/cm}^2 = 10^6 \text{ bar}$$
$$\rho_0 \text{ [g/cm}^3] \times U_s \text{ [10}^5 \text{ cm/s]} \times U_p \text{ [10}^5 \text{ cm/s]} = \rho_0 U_s U_p \times 10^{10} \text{ dyn/cm}^2 = \rho_0 U_s U_p \times 0.01 \text{ Mbar}$$

Therefore:

$$\boxed{P \text{ [Mbar]} = \rho_0 \cdot \frac{\gamma + 1}{2} \cdot U_p^2 \times 0.01}$$

In the $U_p$-$P$ plane, the Hugoniot curve of an ideal plasma is a **parabola** ($P \propto U_p^2$).

---

## 5. Summary: Ideal Plasma Hugoniot Formulas

Given parameters:
- $\rho_0$: initial density (g/cm³)
- $\gamma$: adiabatic index (default $5/3$)

For $U_p \in [0, U_{p,\max}]$, generate Hugoniot data points:

| Physical Quantity | Formula |
|--------|------|
| Shock velocity $U_s$ | $U_s = \dfrac{\gamma+1}{2} U_p$ |
| Pressure $P$ | $P = \rho_0 \cdot \dfrac{\gamma+1}{2} \cdot U_p^2 \times 0.01$ (Mbar) |
| Density $\rho$ | $\rho = \rho_0 \cdot \dfrac{\gamma+1}{\gamma-1}$ (constant, independent of $U_p$) |
| Compression ratio | $\rho/\rho_0 = \dfrac{\gamma+1}{\gamma-1}$ (constant, independent of $U_p$) |

---

## 6. Applicability and Limitations

### 6.1 Applicable Scenarios

- **Fully ionized plasma**: temperature sufficiently high that all electrons are stripped from atoms
- **Low-density foam materials**: e.g., CH foam ($\rho_0 \sim 0.1$ g/cm³) at T > several tens of eV
- **Strong shocks**: $P \gg P_0$, i.e., post-shock pressure much larger than initial pressure

### 6.2 Model Assumptions

1. **Ideal gas behavior**: no inter-particle interaction potential, only kinetic energy contribution
2. **3 degrees of freedom**: only translational degrees of freedom considered; electronic excitation, radiation, etc. are neglected
3. **Strong shock limit**: $P_0 \approx 0$, $E_0 \approx 0$
4. **Chemical equilibrium**: ionization fraction does not vary with shock state (fully ionized)

### 6.3 Limitations

1. **Not applicable to weak shocks**: when $P$ is comparable to $P_0$, the compression ratio is no longer constant; the full Rankine-Hugoniot equations must be used
2. **Not applicable to partial ionization**: if not all material is fully ionized, $\gamma$ will deviate from 5/3
3. **Not applicable in the highly degenerate regime**: when electron degeneracy effects are significant, the equation of state deviates from the ideal gas
4. **Not applicable in the radiation-dominated regime**: at extremely high temperatures where radiation pressure becomes significant, the effective $\gamma$ decreases

---

## 7. Compatibility with Existing Code

### 7.1 Data Structure Compatibility

The ideal plasma Hugoniot data should be fully compatible with the existing `MaterialData` data structure:

```
Up(km/s)  — particle velocity array
Us(km/s)  — shock velocity array
P(Mbar)   — pressure array
rho(g/cm3) — density array (constant = ρ₀ × (γ+1)/(γ-1))
compression — compression ratio array (constant = (γ+1)/(γ-1))
```

### 7.2 Physics Computation Compatibility

The generated ideal plasma curve can be used directly in all existing workflows:

1. **Rayleigh line intersection**: `find_intersections()` — identical to general Hugoniots
2. **Hugoniot reflection**: `reflect_hugoniot()` — mirror symmetry operation independent of material type
3. **Compression ratio calculation**: `compression_ratio(D, up)` — note that for an ideal plasma, the compression ratio determined from the intersection of the Rayleigh line and Hugoniot should approach the theoretical value $(\gamma+1)/(\gamma-1)$ in the strong shock limit, which can serve as a self-consistency check

### 7.3 Required New Parameters

When creating an ideal plasma material, the user needs to provide:

| Parameter | Description | Default |
|------|------|--------|
| $\rho_0$ | Initial density (g/cm³) | No default, must be specified |
| $\gamma$ | Adiabatic index | $5/3$ |
| $U_{p,\max}$ | Maximum particle velocity (km/s) | 200 |
| Material name | Identifier | No default |

---

## 8. Verification

Using the CH foam example from the reference notebook:

- $\rho_0 = 0.089$ g/cm³, $\gamma = 5/3$
- Theoretical compression ratio: $\rho/\rho_0 = 4$
- $U_s = \frac{4}{3} U_p$
- Taking $U_p = 10$ km/s:
  - $U_s = 13.33$ km/s
  - $P = 0.089 \times 13.33 \times 10 \times 0.01 = 0.1187$ Mbar
  - Or directly: $P = 0.089 \times \frac{4}{3} \times 100 \times 0.01 = 0.1187$ Mbar ✓
