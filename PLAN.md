# Analysis plan

Written on 25 October 2026, before any outcome statistics were computed. Before writing it, only structural checks were run on the data: row and column counts, null counts, the range of `time_to_tca`, the list of object types, and CDMs per event. No risk values, threshold crossings, scaling factors or covariance comparisons had been looked at.

Any change made after this file is first committed is listed at the bottom with its date and reason.

## Question

How much should a single probability of collision (Pc) be trusted at the moment an operator has to decide whether to maneuver?

Using ESA's public archive of Conjunction Data Messages (CDMs), this analysis measures:

1. how much Pc moves between decision time and the last CDM before closest approach,
2. how often that movement crosses common maneuver thresholds,
3. how often a low Pc reflects large uncertainty rather than a wide miss (probability dilution),
4. whether the uncertainties reported at decision time are consistent with how the estimates later change, and
5. whether these effects are worse for smaller or poorly characterized objects.

## Data

ESA Kelvins Collision Avoidance Challenge dataset, Zenodo record 4463683 (DOI 10.5281/zenodo.4463683), license CC BY 4.0. File `Collision Avoidance Challenge - Dataset.zip`, md5 `d19dc8875229f2f6893253c38adddc87`.

Primary table: `raw_data/raw_data_2015-2019.gz`, 199,082 CDMs in 15,321 events across 19 missions, received by ESA from 2015 to 2019 and anonymized for release. According to the challenge description (Uriot et al., arXiv:2008.03069), events that already required an avoidance maneuver were removed, and for events with a maneuver, CDMs before the maneuver epoch were removed.

## Definitions

- **r**: the `risk` column, ESA's log10 Pc computed at each CDM epoch.
- **Negligible floor**: for metrics based on differences in r, values below -10 are set to -10, so that changes among negligible values (for example from -30 to -12) do not count as movement.
- **Final CDM**: the last CDM of each event (smallest `time_to_tca`), matching ESA's own definition of the event's final risk. Robustness check: the last CDM with `time_to_tca >= 0`.
- **Decision CDM (primary)**: the latest CDM with `time_to_tca >= 1.0` day, ESA's final decision point. **Secondary**: the latest CDM with `time_to_tca >= 2.0` days, ESA's alert point.
- **Eligible event**: has a decision CDM and at least one later CDM (so the final CDM differs from the decision CDM and has `time_to_tca` below the decision cutoff).
- **Consequential event**: an eligible event with max(r_decision, r_final) >= -6, meaning at least one of the two readings reached the 1e-6 notification level used in the ESA challenge.
- **Thresholds T**: 1e-4, 1e-5 and 1e-6.
- **Dilution region**: a CDM whose `max_risk_scaling` is below 1, meaning the maximum attainable Pc is reached by shrinking the covariance. A low Pc in this region reflects large uncertainty, not a wide miss. Subject to the convention check in H3(a).
- **Radial consistency statistic**: z = (relative_position_r at final − relative_position_r at decision) / sqrt(t_sigma_r² + c_sigma_r²) at decision. The radial axis is shared by both objects at conjunction, so no frame rotation is needed.

## Hypotheses and metrics

**H1, instability.** Among consequential eligible events, report the fraction with |r_final − r_decision| >= 1 (an order of magnitude) and >= 2, with direction (up or down). Expectation: a substantial fraction moves by at least an order of magnitude.

**H2, threshold misclassification.** For each T, the 2×2 table of (r_decision >= log10 T) against (r_final >= log10 T) over all eligible events. Report missed escalations (below T at decision, at or above T at final), false alarms (at or above T at decision, below T at final), and the sensitivity and precision of a decision-time threshold rule measured against the final classification. Also a policy curve: decision thresholds from 1e-3 to 1e-9 against final thresholds of 1e-4 and 1e-5.

**H3, dilution.**
(a) Convention check, which must pass before (b) to (d) are interpreted: across all CDMs, `max_risk_scaling < 1` should go with lower `mahalanobis_distance` than `max_risk_scaling > 1`. For an isotropic two-dimensional encounter the boundary sits near a Mahalanobis distance of sqrt(2). If the relationship is inverted, the reciprocal convention is used and stated. If there is no relationship, H3 is reported as inconclusive.
(b) The fraction of decision CDMs in the dilution region, overall and among those below each T.
(c) Among missed escalations, the fraction whose decision CDM was in the dilution region, compared with events that stayed below T at both times. Expectation: missed escalations are concentrated in the dilution region.
(d) Headroom: among dilution-region decision CDMs below T, the fraction whose `max_risk_estimate` is at or above T.

**H4, consistency of reported uncertainty (radial axis).** If the decision-time covariances were realistic, the update from decision to final should be no larger than the decision-time uncertainty, so std(z) <= 1 and P(|z| > 3) would be about 0.27% for Gaussian errors. Report std(z), a robust spread (1.4826 × median absolute deviation) and the fraction with |z| > 3, overall and by chaser object type. Expectation: std(z) > 1, meaning reported uncertainty is understated. Events with a missing sigma are excluded.

**H5, object type and size.** Repeat H1, H3(b) and H4 by `c_object_type` and by tercile of `c_rcs_estimate` where it is available. Expectation: debris and small radar cross-section objects show more instability, more dilution and less consistent uncertainty.

**D1, descriptive: can Pc be checked against outcomes at this scale?** The sum of final Pc over all events is the number of collisions expected if Pc were calibrated. Report it, together with the number of events above each T, to show how much data an outcome-based check of Pc would need.

## Uncertainty

95% confidence intervals from 5,000 bootstrap resamples of events. Robustness: a bootstrap that resamples missions instead of events, and a per-mission breakdown, so that no single mission drives a result.

## What this analysis cannot show

- There are no collision outcomes in the data. The final CDM is ESA's best estimate, not ground truth.
- Objects too small to track never appear, so the largest blind spot of Pc cannot be measured here.
- The missions are uncrewed ESA and partner spacecraft from 2015 to 2019.
- Anonymization removes absolute times and full states, which limits geometric reconstruction.

## Changes after this commit

None yet.
