# conjunction-pc-audit

An open audit of how probability of collision (Pc) behaves in ESA's public archive of Conjunction Data Messages (2015 to 2019).

Satellite operators decide whether to maneuver mostly by comparing one number, Pc, against a fixed threshold. This repository asks how much that number deserves the trust it gets at the moment of decision: how much it moves before closest approach, how often a low value reflects missing knowledge rather than a safe geometry, and whether the uncertainties behind it hold up.

The analysis plan was written and committed before any results were computed. See [PLAN.md](PLAN.md).

Status: plan committed, analysis in progress.

## Data

ESA Kelvins Collision Avoidance Challenge dataset, Zenodo DOI [10.5281/zenodo.4463683](https://doi.org/10.5281/zenodo.4463683), CC BY 4.0, by T. Uriot, D. Izzo, J. Martinez-Heras, F. Letizia, J. Siminski and K. Merz (ESA Advanced Concepts Team and ESA Space Debris Office). The data is not redistributed here; a script downloads it and checks its checksum.

## License

Code: MIT. The dataset remains under its own CC BY 4.0 license.
