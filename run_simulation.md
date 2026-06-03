# EnergyPlus Simulation Runner Guide

This document describes how to run EnergyPlus simulations on `.idf` files in this project and save the results inside the `runs` directory in folders named after the respective IDF files.

## Runner Script Overview

We have created a helper Python script `run_idf.py` which automates:
1. Resolving the installed EnergyPlus path on Windows (looks for V25-2-0, V25-1-0, etc.).
2. Creating an output subdirectory under the [runs](file:///c:/Users/taegyu/Codes/EnergyPlus_Project1/runs) folder based on the input IDF filename.
3. Invoking the simulation using the `pyenergyplus` API.

---

## How to Run the Simulation

### Option 1: Run with Default Settings
To run the simulation for [260603.idf](file:///c:/Users/taegyu/Codes/EnergyPlus_Project1/260603.idf) with the default Gwangju weather file:

```bash
python run_idf.py
```

### Option 2: Run a Specific IDF File
To run a simulation for a custom IDF file:

```bash
python run_idf.py <path_to_idf_file>
```

*Example:*
```bash
python run_idf.py gl2.idf
```

### Option 3: Run with a Custom Weather (EPW) File
To specify both the IDF file and the weather EPW file:

```bash
python run_idf.py <path_to_idf_file> <path_to_epw_file>
```

*Example:*
```bash
python run_idf.py 260603.idf data/KOR_Kwangju.471560_IWEC (1).epw
```

---

## Output Folder Structure

When you run `run_idf.py <filename>.idf`, a folder will automatically be created under the `runs` directory:

```text
c:\Users\taegyu\Codes\EnergyPlus_Project1\runs\
└── <filename>\
    ├── eplusout.csv (Output variables)
    ├── eplusout.eso (Detailed simulation output data)
    ├── eplusout.err (Error/warning logs)
    ├── eplusout.html (Summary reports)
    └── ... (other EnergyPlus output files)
```

For example, running `python run_idf.py` will generate:
[runs/260603/](file:///c:/Users/taegyu/Codes/EnergyPlus_Project1/runs/260603) containing the results of `260603.idf`.
