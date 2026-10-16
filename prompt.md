Using Build123d, design a bracket that meets all requirements in A15.json. 

Constraints:
For FEA, use CalculiX. You are limited to 30 total modal FEA runs
You have access to a DfM check script for 5 axis CNC manufacturing. You are limited to 30 total DfM script calls. 
If you hit either your FEA or DfM check limits, respond with your best attempt. 
Web search is allowed, however you are unable to download anything. Build123d and CalculiX docs are already cached in your project. 

FEA instructions - "FEA_refrence.png" is a visual summary of FEA requirements. 
Rigid constraints are only applied to bolt holes. 


Orginization: Format - For every geometry iteration, create a new folder labeled iteration_1. Inside each iteration folder, create three folders, one called “DfM_1”, one called “geometry_1”, and a “FEA_1” folder. 
Create a new geometry iteration folder for every design change. 

Keep out zone:
The keep-out zone is a vertical cylinder, 140 mm in diameter and 109.2 mm tall, enclosing the original L-shaped obstruction. It sits above the bracket’s four mounting pads, centered at X = 79.4 mm, Y = 19.5 mm, spanning Z = −77.8 to +31.4 mm in the STEP coordinates. 





Do not respond until you have a bracket that meets all requirements. 



