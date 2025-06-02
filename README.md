# qpansopy
An opensource PANS OPS software implementation based on QGIS

***Note: This code is in development and provided as is, it may contain errors and you are solely resposible for using it. Any feedback is welcome.***

* The implementation is done in a projected coordinate system and currently there is no intention to use a purely geodesic calculation.  
* All computations are done in meters and KTS thus conversions are done when needed.
* Use of references layers vs rubberbands (point/click on map to get values) is currently used, this may be changed in the future.
* PANS OPS has "equivalences" that are not really equivalent like 50 ft = 15 m so you would expect some differences due to this.

## Currently in implementation
***main initial focus is area creation, evaluation to be added at later stage***

### Utilities 
- VSS NPA
- Wind Spiral Utility
### Precision Approach
- ILS Basic Surfaces
- ILS OAS CAT I

## Next Steps 
- CONV VOR Template
- CONV NDB Template
- PBN LNAV (straight to runway)
- PBN intermediate (aligned)
- PBN initial (without automatic connection to the intermediate)

## Roadmap
- Initial focus in correct area creation
- Ability to export tables to Word for creating reports
- Add evaluation of straight segments
- Add logic for evaluation of curves/offsets
