

**Room Arrangement for Inclusive and Supportive Environments**

RAISE is an AI-assisted room-planning software system that generates furniture layouts based on selected mobility, sensory, and tactile accessibility needs.

## Overview

Arranging a room can require repeated trial and error, especially when multiple accessibility needs must be considered simultaneously. Furniture may fit inside a room while blocking the entrance, interrupting a travel path, removing wheelchair turning space, or placing quiet and noisy objects too close together.

RAISE represents room planning as a constraint satisfaction problem. Users provide room dimensions, fixed features, furniture, and an accessibility profile. The program searches for a valid arrangement, displays the resulting layout, and explains which requirements were satisfied.

RAISE was developed in Python and runs in Google Colab.

## Features

- Built-in room presets
- Custom room-design form
- Movable furniture and equipment
- Fixed doors and windows
- Furniture collision detection
- Doorway-clearance checking
- Connected travel-path checking
- Wheelchair turning-space checking
- Essential-furniture reachability
- Tactile-station access
- Separation of quiet and noisy sensory areas
- Labeled room visualization
- Constraint explanations
- Search statistics and layout scores
- Separate results for invalid input, no solution, and search-limit conditions

## Accessibility Profiles

RAISE currently includes the following profiles:

### Mobility

Checks for:

- A usable doorway
- A connected travel path
- Reachable essential furniture
- A clear turning area

### Sensory

Checks for:

- A designated quiet area
- Separation between quiet and noisy or stimulating equipment
- A valid travel path through the room

### Combined

Coordinates mobility, tactile-access, and sensory-separation requirements in one layout.

The profiles are simplified and editable starting points. They are not complete definitions of anyone’s disability or individual accessibility needs.

## AI Techniques

RAISE uses classical artificial intelligence methods rather than machine learning.

### Constraint Satisfaction

Each furniture item is represented as a variable. Its possible positions and orientations form its domain. Accessibility and spatial requirements are represented as constraints.

### Backtracking Search

The solver places furniture one item at a time. When a placement prevents the remaining requirements from being satisfied, it reverses the decision and tries another arrangement.

### Minimum Remaining Values

The improved search selects the furniture item with the fewest currently valid placement options first. This helps expose difficult conflicts earlier.

### Forward Checking

After each placement, the program verifies that every remaining furniture item still has at least one legal position.

### Breadth-First Search

Breadth-first search determines which open floor cells are reachable from the doorway. This is used to evaluate travel-path connectivity and furniture reachability.

## How to Run RAISE

1. Open the notebook in Google Colab.
2. Select **Runtime → Run all**.
3. Wait for the setup cells to finish.
4. Choose a built-in preset or complete the custom room form.
5. Run the selected room-planning cell.
6. Review the generated layout, constraint explanations, and search statistics.

No paid software or specialized hardware is required.

## User Inputs

The custom form allows the user to select or enter:

- Room width and height
- Door coordinates
- Window coordinates
- Movable furniture and equipment
- Accessibility profile
- Basic or improved search
- Maximum number of search attempts

Room coordinates begin at zero. Doors and windows must be placed on an outside edge of the room.

For example, in a room with a width of 10 cells, valid horizontal coordinates range from 0 through 9.

## Movable and Fixed Objects

Doors and windows are treated as fixed room features.

Furniture and equipment are movable objects. Examples include:

- Bed
- Desk
- Chair
- Storage unit
- Tactile or Braille station
- Quiet sensory corner
- Television
- Humidifier
- Other sensory equipment

The solver searches for valid positions and orientations for the movable objects while protecting the fixed features.

## Output

When RAISE finds a solution, it produces:

- A labeled room-layout grid
- Furniture positions and orientations
- Reachable floor cells
- A marked turning area when required
- A list of satisfied accessibility constraints
- Search attempts and backtracking statistics
- An internal layout-preference score

If no valid layout exists, the program reports that no solution was found. If the search stops because it reaches the attempt limit, RAISE reports that separately rather than incorrectly declaring the room impossible.

## Layout Scoring

RAISE ranks only layouts that already satisfy all required constraints. Its internal scoring system considers:

- Furniture distribution
- Placement of beds and storage near walls
- Desk proximity to a window
- Open space near the center of the room

The score is a design heuristic. It is not a measurement of accessibility, usability, safety, or human preference.

## Example Layout

![Example RAISE layout](images/raise_combined_layout.png)

_Add a screenshot of the combined-profile layout to an `images` folder and use its actual filename here._

## Project Files

- `RAISE_Room_Planner.ipynb` — main Google Colab notebook
- `README.md` — project description and instructions
- `images/` — example room layouts and figures
- `LICENSE` — software license, if included
- `paper/` — optional PDF of the accompanying writing sample

## Limitations

RAISE is an academic software prototype.

- It uses a simplified grid representation.
- Its current profiles cover selected mobility, tactile, and sensory considerations.
- Sensory distance is a spatial approximation and does not model actual acoustics.
- The program has not yet been evaluated with participants.
- The internal score does not represent human accessibility or preference.
- Individual users may require different measurements or conditions.

RAISE does not provide architectural, medical, safety, or ADA certification.

## Future Work

Future development could include:

- User-controlled accessibility rules instead of broad profile labels
- Smaller measurement increments
- Door-swing and approach-direction modeling
- Reach-range and transfer-space requirements
- Multiple entrances
- Lighting and sound-source modeling
- Adjustable preference weights
- Explanations of which constraints caused a room to be impossible
- Participatory evaluation with disabled users and relevant practitioners

## Research Paper

An accompanying HCI case study describes RAISE’s motivation, design, AI formulation, software evaluation, limitations, and future research directions.

_Add the writing-sample PDF or its link here if you decide to make it public._

## Author

**Basbo Ayelazono**  
Computer Science, Bioinformatics, and Integrated Biology  
Dakota State University

## License

This project is available under the MIT License.

_Remove this section if you decide not to include a license._
