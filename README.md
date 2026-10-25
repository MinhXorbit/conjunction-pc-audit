# conjunction-pc-audit

An open audit of how probability of collision (Pc) behaves in ESA's public archive of Conjunction Data Messages (2015 to 2019).

Satellite operators decide whether to maneuver largely by comparing one number, Pc, against a fixed threshold. This repository asks how much that number deserves the trust it gets at the moment of decision: how much it moves before closest approach, how often a low value reflects missing knowledge rather than a safe geometry, and whether the uncertainties behind it hold up.

The analysis plan was written and committed before any results were computed: see [PLAN.md](PLAN.md) and the commit history. Results are in [FINDINGS.md](FINDINGS.md).

## Main results

From ESA's final decision point, one day before closest approach:

- **Pc moved by 10× or more in 48.5% of the conjunctions that mattered** (those reaching 1e-6), and by 100× or more in 41.4%.
- **At a 1e-5 threshold, about half of the decision-time alerts ended below it, and about one in six events that ended above it had been below it.** Four of those had a decision-time Pc under 1e-9.
- **Probability dilution affects 5% of decision-time CDMs** and accounts for a minority of the missed escalations.
- **3.0% of radial updates exceed 3σ of the reported uncertainty, about 11 times what consistent Gaussian uncertainty allows.** Active satellites show the heaviest tails.
- **Summed over all 15,321 conjunctions, the final Pc values add up to 0.049 expected collisions.** This archive cannot test Pc against outcomes.

Two planned predictions did not hold, and FINDINGS.md says so: dilution does not explain most misses, and smaller objects are not worse than larger ones.

## Reproduce

```bash
pip install -r requirements.txt
python scripts/fetch_data.py                 # downloads from Zenodo and checks the md5
python scripts/run_audit.py --data "data/raw/Collision Avoidance Challenge - Dataset/raw_data/raw_data_2015-2019.gz"
python scripts/make_figures.py
python -m pytest -q                          # unit tests on synthetic data
```

The analysis runs in under a minute on a laptop. Fixed seeds make the bootstrap intervals reproducible.

## Layout

```
PLAN.md                 analysis plan, committed before any results
FINDINGS.md             results in plain language, with figures
pc_audit/               event extraction, metrics, bootstrap
scripts/                fetch_data.py, run_audit.py, make_figures.py
results/                results.json and derived tables
figures/                PNG and PDF figures
tests/                  unit tests
```

## Data

ESA Kelvins Collision Avoidance Challenge dataset, Zenodo DOI [10.5281/zenodo.4463683](https://doi.org/10.5281/zenodo.4463683), CC BY 4.0, by T. Uriot, D. Izzo, J. Martinez-Heras, F. Letizia, J. Siminski and K. Merz (ESA Advanced Concepts Team and ESA Space Debris Office). The raw data is not redistributed here. `scripts/fetch_data.py` downloads it and checks its checksum. The tables in `results/` are derived from it and carry the same attribution.

## Credits

Maintained by Minh Nguyen (xOrbita). Analysis code and documentation were developed with assistance from Claude (Anthropic).

## License

Code: MIT. The dataset and anything derived from it remain under CC BY 4.0.
