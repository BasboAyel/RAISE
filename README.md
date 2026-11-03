# RAISE: Room Arrangement for Inclusive and Supportive Environments

RAISE is a small, inspectable room-planning tool that arranges furniture around explicit accessibility-related rules. A user describes a room, its fixed features (doors and windows), movable furniture, and an accessibility profile. RAISE searches for a layout, then returns either a labeled plan with a constraint-by-constraint explanation or a distinct failure status.

It is a research prototype that accompanies an HCI case study. It runs entirely in Google Colab with no paid software or special hardware.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR-USERNAME/YOUR-REPO-NAME/blob/main/raise_room_planner.ipynb)

> **Scope.** RAISE is a classroom-scale planning model on a one-foot grid. It is **not** an ADA, architectural, medical, or safety certification, and its results are software results, not evidence of human usability or outcomes. A passed check means only that the encoded condition holds in the model.

## What it does

- **Profiles as editable rules.** Mobility, sensory, and combined presets switch on explicit checks: a three-cell doorway and route clearance, essential-item reachability, a door-free 5×5-cell turning square (a proxy for a 60-inch turning circle), tactile reach, and quiet/noisy zone separation. A custom form lets you change the room, objects, and profile.
- **Hard constraints vs. preferences.** Required conditions gate validity. A separate, transparent layout score ranks only layouts that already pass every constraint.
- **Distinct outcomes.** The solver reports `invalid_input`, `solved`, `no_solution`, or `limit_reached`, so an exhausted search is never confused with an interrupted one.
- **Visible reasoning.** Output includes a labeled grid, constraint results, search metrics, and score components.

## Techniques

Constraint satisfaction with backtracking search, optional minimum-remaining-values (MRV) ordering, forward checking, breadth-first route analysis, and an explainable preference score.

## Quick start

1. Click the **Open In Colab** badge above (or upload `raise_room_planner.ipynb` to Colab).
2. Run the cells in order. The core model cell defines everything the later cells use.
3. Choose a preset in the preset cell, or enter your own room in the custom form.

## Reproducing the evaluation

- **Section 8** runs the first-solution comparison of basic backtracking and MRV plus forward checking, and the best-of-50 comparison, for the selected preset.
- **Section 8b** runs the 30-seed random-sampling baseline. It compares the deterministic score-guided best of 50 valid layouts with the best of 50 layouts drawn by randomized sequential placement with rejection (the sampler is not uniform over all valid layouts). Set `N_SEEDS` lower for a quick check. It takes about two minutes for all three rooms at 30 seeds.

Search counts (attempts, backtracks) are deterministic. Elapsed time depends on the environment.

## Limitations

- Evaluation is software-based on simulated rooms. No participant or practitioner evaluation has been done.
- The one-foot grid is coarse. Door swing, approach direction, transfer space, and individual reach ranges are not modeled, and the turning-space test does not cover every permitted T-shaped configuration.
- Sensory distance is a spatial proxy, not an acoustic or perceptual measurement.
- The layout score reflects designer-authored heuristics and is not a measure of human preference.
- Constraint checking is not independently implemented: the final validation reuses the search's constraint routines.

Participatory work with disabled people and practitioners is needed to decide which requirements, explanations, and controls are actually useful.

## License

MIT. See [LICENSE](LICENSE).
