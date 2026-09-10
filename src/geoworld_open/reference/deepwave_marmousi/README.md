# Pinned Deepwave Marmousi 1 reference

Classification: **PUBLIC_REFERENCE / PUBLIC_BENCHMARK**. The two example programs
are unmodified upstream files, not original GeoWorld numerical implementations.
Their MIT copyright notice is in `LICENSE.txt`. The surrounding recorder,
definition and verifier are GeoWorld benchmark infrastructure; private product
interpretation and execution policy remain in `geoworld`.

Upstream: [Deepwave](https://github.com/ar4/deepwave), v0.0.26, peeled commit
`7dbaeda5fdfbff2a6d579dcc9f7f18488c5e6084`.

- [Forward modelling with Marmousi](https://ausargeo.com/deepwave/example_forward_model)
- [Reducing memory usage by accumulating gradients over batches](https://ausargeo.com/deepwave/example_rtm)

The source SHA-256 values are checked by `runner.py` before execution. Do not
import the example modules: like the original programs, importing executes them.

## Scientific identity

Marmousi **1**, not Marmousi 2: 2301 × 751 float32 values, axis order `(x, depth)`,
4 m grid spacing, 1500–5500 m/s. The expected binary SHA-256 is
`f4302792e84bb7ddbdc9d4d0f963b9df32d9f648960084884127e186119b99dd`.
Raw binary does not encode shape, units or axes: these come from the pinned
example. No density file is used by this constant-density acoustic experiment.
Dataset redistribution rights are separate from the Deepwave software license;
no Marmousi binary is included in this package.

The forward program uses 115 shots in one scalar call, 384 receivers, a 25 Hz
Ricker, 750 samples, 4 ms requested sampling, accuracy 8 and PML frequency 25 Hz.
The installed Deepwave defaults are recorded rather than inferred from the UI.

RTM smooths **slowness** with sigma 40 original cells (160 m), then decimates by
two to the official 1151 × 376, 8 m migration grid. This decimation is part of
the exact upstream reference, not a reduced adaptation. RTM leaves accuracy
unspecified: Deepwave 0.0.26 uses **4**, not forward's 8. Its direct-arrival mute
has a 100-sample flat region, two 200-sample cosine tapers and 1700 m/s arrival
velocity. It does **not** use LSRTM background subtraction. There are 46 loop
batches, 39 nonempty, up to 3 shots each; per-batch mean losses accumulate
gradients before **one** SGD update at learning rate 1e9. Preserve the final
one-shot batch's weighting too.

## Standalone execution

Use an environment with Deepwave 0.0.26, PyTorch, NumPy, SciPy and Matplotlib.
These remain optional, not base public-client dependencies. Run the recorder
file directly; it imports no GeoWorld service or private code. From private
`geoworld`, after reviewing host resources:

```bash
timeout --signal=TERM --kill-after=10s 3610s .venv/bin/python \
  ../geoworld-open/src/geoworld_open/reference/deepwave_marmousi/runner.py forward \
  --vp /path/to/Marmousi1/vp.bin \
  --output runs/deepwave-reference-20260910/standalone-forward \
  --wall-seconds 3600 --memory-gib 20

timeout --signal=TERM --kill-after=10s 3610s .venv/bin/python \
  ../geoworld-open/src/geoworld_open/reference/deepwave_marmousi/runner.py rtm \
  --vp /path/to/Marmousi1/vp.bin \
  --forward runs/deepwave-reference-20260910/standalone-forward \
  --output runs/deepwave-reference-20260910/standalone-rtm \
  --wall-seconds 3600 --memory-gib 20
```

Existing output directories are refused, never overwritten. `timeout` is the
external hard wall guard (a Python alarm alone may wait for a native kernel).
The private API uses its existing killable worker for the same hard boundary.
A killed/failed/incomplete run is not a reproduced reference. A short resource
probe is always `reduced_reference_adaptation`, never acceptance evidence.

The recorder calls the unchanged program via `runpy`, retaining its default
CUDA-if-available/otherwise-CPU selection and numerical calls. It selects Agg
for noninteractive plots and adds raw arrays, settings, version/runtime/memory
metadata and checksums. The original plots are retained; `plotting_image.npy`
is explicitly a transposed/clipped derivative of the separately saved raw RTM
image. Extra velocity/acquisition plots do not change numerical results.
`representative_shot.npy` is zero-based shot 57 in the forward run and shot 0
in the RTM run, matching the respective upstream diagnostic figures. All 115
shots remain available in `marmousi_data.bin`; the representative image is not
a reduced-acquisition experiment.

`compare_runs` requires equal settings, observed-data identity, exact geometry,
wavelet, velocity and mask, and finite raw masked-data/image/gradient arrays
within `rtol=1e-5, atol=1e-7`. Numerical agreement is not inferred from JPEGs.
