# Project specification
Project requirements will be recorded here.

# Beam Designer

## Purpose
A Python desktop application built with Tkinter that displays shear, moment,
and deflection diagrams for a beam and checks whether the beam is strong and
stiff enough.

## Inputs
- Support type: Simply supported or Cantilever (fixed at the left end).
- Span: 4 to 40 ft, set with a slider and a number box that stay in sync.
- Loads, listed in a panel where each can be edited or removed:
  - Point loads: magnitude (kips, downward positive) and position (ft).
    A new point load starts at midspan (at the free end of a cantilever).
  - Uniform loads: magnitude (kips/ft) and start and end positions (ft).
  - "Add point load" and "Add uniform load" buttons.
  - Point loads can also be dragged along the beam in the drawing,
    snapping to 0.25 ft.
  - Loads that extend past the end of the beam are cut off at the end.
- Material and section, from these tables:

  Steel W-shapes (E = 29,000 ksi, allowable bending stress Fb = 30 ksi;
  section dimensions in inches):
  d is depth, bf is flange width, tf is flange thickness, and tw is web
  thickness.

  | Section | d | bf | tf | tw | Ix (in^4) | Sx (in^3) | Weight (lb/ft) |
  |---------|---:|---:|---:|---:|----------:|----------:|---------------:|
  | W8x10   | 7.89 | 3.940 | 0.205 | 0.170 | 30.8 | 7.81 | 10 |
  | W10x12  | 9.87 | 3.960 | 0.210 | 0.190 | 53.8 | 10.9 | 12 |
  | W12x26  | 12.22 | 6.490 | 0.380 | 0.230 | 204 | 33.4 | 26 |
  | W14x22  | 13.74 | 5.000 | 0.335 | 0.230 | 199 | 29.0 | 22 |
  | W16x26  | 15.69 | 5.500 | 0.345 | 0.250 | 301 | 38.4 | 26 |
  | W18x35  | 17.70 | 6.000 | 0.425 | 0.300 | 510 | 57.6 | 35 |
  | W21x44  | 20.66 | 6.500 | 0.450 | 0.350 | 843 | 81.6 | 44 |
  | W24x55  | 23.57 | 7.005 | 0.505 | 0.395 | 1350 | 114 | 55 |

  Douglas Fir-Larch No. 2 lumber (E = 1,600 ksi, Fb = 0.900 ksi).
  Section names are nominal sizes; b and d are actual dressed dimensions
  (width and depth) in inches.

  | Section | b | d | Ix (in^4) | Sx (in^3) |
  |---------|--:|--:|----------:|----------:|
  | 2x8     | 1.50 | 7.25 | 47.63 | 13.14 |
  | 2x10    | 1.50 | 9.25 | 98.93 | 21.39 |
  | 2x12    | 1.50 | 11.25 | 177.98 | 31.64 |

- Deflection limit: L/240 or L/360 (default L/360).
- Self-weight is ignored.

## Calculations
- Use ASD with the entered service loads representing the combined D + L
  case; do not generate other load combinations or include beam self-weight
- Calculate reactions, shear, moment, and deflection
- Check bending stress, fb = M/S, against the applicable allowable stress
- Compare deflection in inches to the selected L/240 or L/360 limit
  (default L/360)
- Assume steel sections are compact and fully laterally braced; do not check
  buckling

## Outputs
- The beam with its loads, and the three diagrams
- A dotted vertical position marker synchronized across the beam and all
  three response diagrams while the pointer is over any diagram
- A dimensioned cross-section preview in Beam setup: steel W-shapes show d,
  bf, tf, and tw; lumber shows actual dressed b and d dimensions
- Pass or fail for bending and deflection
- A pass is not a complete structural design approval

## Look and feel
Clean and professional Tkinter window, with an example beam loaded when it
opens.
- Separate buttons add point loads and uniform loads to the editable load panel.

## Validation
1. Simply supported, 20 ft, W12x26, uniform 1 kip/ft over the full span:
   reactions 10 k and 10 k; max shear 10 k; max moment 50.0 kip-ft at
   10 ft; fb = 17.96 ksi; max deflection 0.609 in at 10 ft; L/360 =
   0.667 in; both checks pass.
2. Simply supported, 20 ft, W12x26, point load 10 k at 5 ft: reactions
   7.5 k (left) and 2.5 k (right); max moment 37.5 kip-ft at 5 ft;
   fb = 13.47 ksi; max deflection 0.340 in at 8.82 ft.
3. Cantilever, 10 ft, W12x26, point load 5 k at the free end: reaction
   5 k and fixed-end moment 50 kip-ft; max deflection 0.487 in at the free
   end (PL^3/3EI); L/360 = 0.333 in, so deflection fails.
4. Simply supported 12 ft 2x10 joist, uniform 0.05 kip/ft: max moment
   0.90 kip-ft; fb = 0.505 ksi; max deflection 0.147 in; both pass.

## Out of scope
Continuous beams, load combinations, shear stress, self-weight, and buckling.

## App build sequence
1. Create the Tkinter desktop window with the beam and diagram display,
   controls, results, and a preloaded example.
2. Set up the app's beam and load state, then connect the support-type and
   span controls, including the 4 to 40 ft range and synchronized slider and
   number box.
3. Add material and section selection from the specified tables, and add the
   L/240 or L/360 selector with L/360 as its default.
4. Build the editable load panel: add, edit, and remove point and uniform
   loads; support dragging point loads with 0.25 ft snapping; and limit load
   extents to the beam.
5. Implement the structural calculations for the entered D + L service-load
   case: reactions, shear, moment, deflection, peak values, and locations.
   Apply consistent conversions between ft, kip, ksi, and inches.
6. Draw the beam and its point and uniform loads, plus the shear, moment, and
   deflection diagrams. Keep the diagrams and displayed results synchronized
   with changes to the beam, material, loads, and deflection limit.
7. Show bending and deflection results as pass or fail against the selected
   allowable stress and deflection limit. State the checks and exclusions
   clearly; a pass is not complete structural design approval.
8. Verify the four validation cases above, then check boundary behavior such
   as loads at supports or the cantilever free end, partial loads at the beam
   end, load editing/removal, and the span limits.
