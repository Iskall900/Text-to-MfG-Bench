# A15 selected FEA evidence

See `/workspace/FINAL_REPORT.md` for the complete assumptions, loads, supports, convergence and limitations.

Selected run: `model_complete/solve.inp`, `.dat`, `.frd`, `ccx_stdout.log`, `results.json`, `mesh_diagnostics.json`, `load_cases.json`, `first_mode_shape.csv`. Mesh convergence across identical geometry: `../..` iteration8/9/10 and `convergence.json` here.

Only T bores are fixed. The point mass is at the offset CG. No intrinsic rotational inertia was invented. Numerical mass/modal/yield screening passes; keep-out registration and peak-stress convergence prevent overall acceptance.
