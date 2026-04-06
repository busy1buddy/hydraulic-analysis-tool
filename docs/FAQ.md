# Frequently Asked Questions

## Getting Started

### What does the welcome dialog do?
The welcome dialog appears on first launch when no network is loaded. It offers
three quick-start options: Open Demo Network (loads the demo with WSAA violations),
Open Network File (opens a file dialog), and View Tutorials (opens the tutorials folder).
Tick "Don't show this again" to skip it on future launches.

### How do I open my first network?
Use **File > Open** (Ctrl+O) and select an `.inp` file. EPANET `.inp` files are
the standard format used by WaterGEMS, InfoWater, and other hydraulic software.
Then press **F5** to run steady-state analysis.

### Why does my network look like a straight line?
Your `.inp` file may not have coordinate data in the `[COORDINATES]` section.
Without coordinates, all nodes are placed at (0,0). Add coordinates in the `.inp`
file or use Edit Mode to arrange nodes manually.

## Projects and Saving

### How do I save my project?
Use **File > Save As** (Ctrl+Shift+S) to save as a `.hap` project file. This saves
your network path, analysis results, slurry parameters, scenarios, and UI settings.
Use **File > Save** (Ctrl+S) to save the network as a standard `.inp` file.

### What is a .hap file?
A `.hap` (Hydraulic Analysis Project) file is a JSON project file that stores:
- Path to the `.inp` network file
- Last analysis results (pressures, flows, compliance)
- Slurry parameters (if active)
- Scenario definitions
- UI settings (colour mode, slurry mode)

You can open a `.hap` file with **File > Open** just like an `.inp` file.

### Why does it say "Network Modified" when I open a .hap file?
The `.hap` file records when the `.inp` file was last modified. If someone changed
the `.inp` file after the project was saved, the tool warns you that the saved
results may not match the current network. Press **F5** to re-run analysis.

## Analysis

### Why does my pressure show negative?
Negative pressure means the junction elevation is higher than the hydraulic grade
line (HGL). This indicates insufficient head to supply that node. Common causes:
- Reservoir head too low for the network elevation
- Pipe too small for the demand (high friction loss)
- Pump not providing enough head

### Why is slurry headloss so much higher than water?
Slurry (non-Newtonian fluid) has much higher viscosity and yield stress than water.
A typical mining slurry at 30% solids by volume can have 5-20x higher headloss
than water at the same flow rate. This is physically correct — it's why slurry
pipelines use larger pipes and higher-pressure pumps.

### How do I compare slurry vs water headloss?
1. Load your network and press **F5** for water analysis
2. Note the headloss values in the pipe results table
3. Enable **Analysis > Slurry Mode** and set parameters via **Analysis > Slurry Parameters**
4. Press **F5** again — the headloss column now shows slurry values
5. Compare the two headloss columns (the header changes to "Headloss Slurry (m/km)")

### What does the Todini resilience index mean?
The Todini index (0-1) measures how much surplus pressure the network has above
the minimum service requirement. Higher is better:
- A (>0.50): Excellent redundancy — multiple supply paths
- B (>0.30): Good redundancy
- C (>0.15): Moderate — adequate for most networks
- D (>0.05): Low — limited redundancy
- F (<0.05): Very low — network is fragile

### How accurate is the transient analysis?
The transient (water hammer) analysis uses the Method of Characteristics (MOC)
solver from TSNet. It is accurate for simple valve closure and pump trip scenarios.
Known limitations:
- Column separation (vapour cavities) modelling is approximate
- Complex valve characteristics (non-linear closure) require careful setup
- Network topology must be fully connected

### Can I trust this tool for engineering sign-off?
The tool uses the same EPANET 2.2 solver used worldwide for water distribution
analysis. All calculations are verified against hand calculations and published
benchmarks. However, the engineer is always responsible for:
- Verifying input data accuracy
- Checking results against engineering judgement
- Applying appropriate safety factors
- Ensuring compliance with local standards (WSAA WSA 03-2011)

## Troubleshooting

### "No network loaded" error
Use **File > Open** (Ctrl+O) to load an `.inp` or `.hap` file first.

### Solver won't converge
Check for:
- Disconnected nodes (use **Tools > Analyse Topology**)
- Zero-diameter pipes
- Extremely high demands relative to pipe capacity
- Missing reservoir or tank (no pressure source)

### Report generation fails
Ensure you have run an analysis first (F5). Reports require analysis results.
If generating PDF, ensure `fpdf2` is installed (`pip install fpdf2`).
