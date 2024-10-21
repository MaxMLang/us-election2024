# 🗳️ 2024 U.S. Presidential Election Model

![US Flag](https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg)

### Predicting the Future of American Politics 🇺🇸

Welcome to the **2024 U.S. Presidential Election Model** project! This project uses  **Hierarchical Bayesian Regression**  to forecast the outcome of the 2024 U.S. presidential election. I use data from multiple pollsters and key control variables, to make robust and bounded predictions of the election outcome in each state.

---

## 📢 Disclaimer

> **This project is developed for personal and academic purposes only. It is not affiliated with any political campaign, organization, or governmental entity. The model and its predictions are purely exploratory and for research purposes, with no intention to influence or intervene in the 2024 U.S. Presidential Election.**
> 
> **I remain completely neutral in this project, with no bias toward any political party or candidate.**

---

## 📊 Methodology

my model is based on:
- **Hierarchical Bayesian Model**: Allows state-level variations to account for unique characteristics of each state's electorate.
- **Beta Regression**: Ensures bounded predictions between 0 and 100%.
- **Control Variables**: Factors like pollster effects, survey mode, and voter population are controlled to improve accuracy.

For more details on the methodology, check out the [Methodology Section](#).

---

## 🚀 Key Features
- **Daily Updates**: The model is updated daily with new polling data using automated workflows.
- **State-by-State Forecasts**: Detailed predictions for each state in the Electoral College.
- **Interactive Visualizations**: Coming soon!

---

## 🔧 How It Works

This project leverages the following key components:
- **Python 3.11**: The project is built using the latest version of Python.
- **Dash Framework**: For visualizing the predictions and creating interactive elements.
- **GitHub Actions**: For automating daily updates with fresh polling data.

To run the project locally, follow these steps:
1. Clone the repository:
    ```bash
    git clone https://github.com/MaxMLang/us-election.git
    ```
2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3. Run the application:
    ```bash
    python app.py
    ```

---

## 🛠️ Automated Daily Update Workflow

This project is powered by GitHub Actions to automatically update polling data and commit changes to the repository daily. The workflow is scheduled to run every day at **12:00 PM UTC**.

For more information, see the `update_prior_information.yml` in the `.github/workflows/` directory.

---


**Credits**:
Thank you to acbass49 which published a similar approach and was my inspiration.

---

🇺🇸 **2024: Make your vote count!**
