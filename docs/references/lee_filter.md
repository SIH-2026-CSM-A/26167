# Lee Filter (SAR Speckle Suppression)

> [!IMPORTANT]
> This document was built fresh for ROHAN-005. The ticket's premise — that
> Lee/MMSE content was already cited in prior session notes — did not hold
> up on verification: no prior source document containing this content was
> ever found, in this repo or elsewhere. It supersedes the from-memory
> Lee/MMSE description in `session-log/rohan.md` from ROHAN-001, which
> explicitly did not attempt to reconstruct the formula from memory once its
> intended source proved unreachable. No specific section of any document is
> named as that unreachable source here, since its content was never read.

## Formula

Applied in the **linear intensity domain**, not dB:

```
output = m + k(z - m)
```

- `z` — observed speckled intensity at the pixel
- `m` — local mean over the filter window
- `k` — `(σ²_l − σ²_n) / σ²_l`, where:
  - `σ²_l` — local variance in the window
  - `σ²_n` — a priori speckle variance

### Boundary behavior

- Homogeneous regions (`σ²_l ≈ σ²_n`) → `k ≈ 1` → strong smoothing.
- Heterogeneous/edge regions (`σ²_l >> σ²_n`) → `k ≈ 0` → near pass-through.

## Sources

**Primary source (VERIFIED):**
Lee, J.-S. (1980), "Digital Image Enhancement and Noise Filtering by Use of
Local Statistics," *IEEE Transactions on Pattern Analysis and Machine
Intelligence*, Vol. PAMI-2, No. 2, pp. 165–168.

**Secondary/implementation source (VERIFIED):**
torchgeo GitHub issue #3645
(https://github.com/torchgeo/torchgeo/issues/3645) — speckle modeled as
multiplicative Gamma-distributed noise (mean 1, variance `1/L` for an
L-look intensity image); their reference implementation validated the LMMSE
update against `scipy.ndimage.uniform_filter` to ≤1e-5 agreement.

## Rejected citation

An arXiv ID was investigated for this document and found off-topic: Ghosh et
al. 2023, on Sentinel-1 flood-mapping data cubes — unrelated to the Lee
filter formula itself. **Deliberately not cited here** — noted explicitly so
it isn't re-added by a future pass mistaking topical adjacency (both concern
Sentinel-1 SAR) for relevance to this specific formula.
