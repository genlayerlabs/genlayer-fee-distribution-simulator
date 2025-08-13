# Developer Setup Guide

This guide provides step-by-step instructions for setting up the GenLayer Fee Distribution Simulator development environment.

## Prerequisites

Before you begin, ensure you have the following software installed on your system:

-   **Git**: For cloning the repository.
-   (Optional) **Miniconda** or **Anaconda**: For managing Python environments and dependencies. We recommend Miniconda for a lightweight setup.

## Step 1: Clone the Repository

Open your terminal and clone the project repository from GitHub:

```bash
git clone <repository_url>
cd genlayer-fee-distribution-simulator
```

## Step 2: Set Up the Conda Environment

We use Conda to create an isolated Python environment. This ensures that all developers are using the same dependency versions and avoids conflicts with other projects.

1.  **Activate your Conda installation**. This command may vary based on your OS and installation:
    ```bash
    # Example for Linux/macOS
    source ~/miniconda3/bin/activate
    ```

2.  **Create and activate the dedicated environment** for the simulator. We'll name it `consensus-simulator`:
    ```bash
    conda create -n consensus-simulator python=3.9
    conda activate consensus-simulator
    ```
    You should see your terminal prompt change to `(consensus-simulator)`.

## Step 3: Install Dependencies

All required Python packages are listed in the `requirements.txt` file. Install them using pip:

```bash
pip install -r requirements.txt
```

## Step 4: Verify the Installation

To ensure everything is set up correctly, run the full test suite using `pytest`.

1.  From the project's root directory, run:
    ```bash
    pytest
    ```

2.  You should see output indicating that all tests have passed. A successful run will end with a message similar to this:
    ```
    =========================== 146 passed in 27.18s ===========================
    ```
    The exact number of tests and time may vary.

3.  As an additional check, run one of the example scripts:
    ```bash
    python examples/01_basic_transaction.py
    ```
    This should execute without errors and print a series of formatted tables to your console, ending with "TRANSACTION COMPLETE".

## Development Workflow & Best Practices

-   **Running Tests**: The test suite is the primary way to verify changes. To get detailed output while developing, run tests with verbose flags:
    ```bash
    # This command is very useful for debugging
    pytest -s --verbose-output --debug-output
    ```

-   **Using Scripts**: The `scripts/` directory contains powerful tools for analysis and generation. For example, to see all possible transaction paths and their outcomes:
    ```bash
    # Generate JSON test vectors for all paths up to length 7
    python scripts/01_generate_test_vectors.py --max-length 7
    ```

-   **AI-Assisted Development**: If you are using an AI assistant like Claude, refer to `CLAUDE.md` for specific instructions and context about the codebase.

-   **Documentation**: Before diving deep into the code, it is highly recommended to read the documentation in the `docs/` directory, especially `ARCHITECTURE.md` and `INVARIANTS.md`.

## Troubleshooting

### `ModuleNotFoundError: No module named 'src.fee_simulator'`

This error typically occurs if you are not running `pytest` or Python scripts from the **project's root directory**.

-   **Solution**: Ensure your terminal's current working directory is `genlayer-fee-distribution-simulator/` before running any commands.

### Conda Environment Not Found

If you get an error like `CondaValueError: Environment not found`, it means the `consensus-simulator` environment is not active or was not created correctly.

-   **Solution**:
    1.  Make sure you have activated the environment: `conda activate consensus-simulator`
    2.  If it doesn't exist, recreate it following the instructions in **Step 2**.
