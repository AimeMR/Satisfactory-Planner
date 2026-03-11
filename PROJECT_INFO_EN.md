# Satisfactory Planner 🚀🏙️

A sophisticated, node-based factory planning application for **Satisfactory**, designed to help Pioneers design, optimize, and visualize their production lines with precision.

> **🚀 Project Evolution Notice:** The current state of the application serves as the interactive foundation. Moving forward, the project is evolving into an **Automated Factory Generator**. The app will ask the user what end material they want to produce (and at what rate), and it will automatically create, connect, and optimize all the necessary machine lines required to build it.

## 🌟 Key Features

- **Interactive Canvas**: A powerful node-based editor using `PySide6` for placing and connecting production machines.
- **Real-time Statistics**: Instant calculation of production/consumption ratios, item flow (items/min), and power requirements.
- **Complete Database**: Pre-loaded with all materials, machines, and recipes from **Tiers 1 to 8** and **Phase 4** of the Space Elevator.
- **Multi-Database Support**: Organize your workflows into separate `.db` files managed within the `databases/` directory.
- **Custom Elements**: Easily add your own custom Materials, Machines, and Recipes directly from the UI to plan modded or hypothetical setups.
- **Multi-Project Support**: Create, save, and switch between multiple factory designs seamlessly within any database.
- **Customizable UI**: 
    - **Global Visibility**: Toggle stats for power, inputs, outputs, and belt flow via a sleek glassmorphism menu.
    - **Optimized Workspace**: Clean top toolbar with consolidated project actions, line styling, and a collapsible sidebar with a sticky toggle button.
    - **Multi-Language**: Fully localized in English and Spanish.
    - **Isolation**: Each project has its own isolated environment for machine placement and connections.

## 🛠️ Technical Stack

- **Languge**: Python 3.10+
- **UI Framework**: PySide6 (Qt for Python).
- **Database**: SQLite with a multi-input/output schema for complex recipes.
- **Architecture**: Separated Logic (calculations), UI (nodes/scene), and Database (CRUD/seeding) layers.

## 📁 Project Structure

- `databases/`: Directory where all SQLite database files (like `satisfactory.db`) are stored.
- `database/`: SQLite schema, seeding logic (`seed_data.py`), multi-db management, and CRUD operations (`crud.py`).
- `ui/`: Main window, custom node graphics (`machine_node.py`), and connection rendering.
- `logic/`: Calculation engine for production rates and efficiency.
- `i18n/`: Translation keys and localization management.

## 🚀 How to Run

1. **Install Dependencies**:
   ```bash
   pip install pyside6
   ```
2. **Launch Application**:
   ```bash
   python main.py
   ```

---
*Built for the community of Pioneers. Efficiency first!*
