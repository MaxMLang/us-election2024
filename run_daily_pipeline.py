from election_helpers import load_polling_data, \
    simulate_election_states, fit_bhm, \
    simulate_election, get_credible_interval, \
    fit_bhm_custom_belief, update_priors, \
    fit_bayes_beta, update_custom_priors
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

reset_priors = False
reset_tracker = False

# Fetch Data
y_vec, x_matrix, state_dict = load_polling_data()
priors = pd.read_csv('./data/priors.csv')
priors.sd = priors.sd * 50 # added this because priors were too strong

# Estimate Model
if reset_priors:
    model, trace = fit_bhm(y_vec, x_matrix, state_dict)
    update_priors(trace, state_dict)
if not reset_priors:
    model, trace = update_custom_priors(y_vec, x_matrix, state_dict, priors)
    update_priors(trace, state_dict)

# Predict State Level Probabilities
preds = simulate_election_states(model, state_dict, x_matrix, trace)

# Run Presidential Simulations
win_perc, sim_data = simulate_election(preds, 50000)

# A Few Post-Processing Steps
sim_data = sim_data.assign(winner = lambda x:np.where(x.winner == 0, "Harris", "Trump"))
to_join = pd.read_csv('https://raw.githubusercontent.com/jasonong/List-of-US-States/master/states.csv')
prob_data = pd.DataFrame({
    'State':list(preds.keys()),
    'Trump Win Prob.':list(preds.values())
}) \
    .merge(to_join, on='State') \
    .assign(State = lambda x:x.Abbreviation) \
    .drop(columns = ['Abbreviation'])

# Calculate Simulation Confidence Interval
LB, UB = get_credible_interval(sim_data)

# Add new row to tracker
if reset_tracker:
    current_date = datetime.now().date()

    tracking_data = pd.DataFrame({
        'Candidate':['Trump', 'Harris'],
        'Win Percentage':[win_perc, 1-win_perc],
        'Date' : current_date,
        'LB' : [LB,(1-win_perc)-(win_perc-LB)],
        'UB' : [UB,(1-win_perc)+(UB-win_perc)]
    })
else: 
    tracking_data = pd.read_csv("./data/tracking_data.csv")
    tracking_data = tracking_data.assign(Date = pd.to_datetime(tracking_data['Date'], format='mixed'))
    current_date = datetime.now().date()

    new_row = pd.DataFrame({
        'Candidate':['Donald Trump', 'Kamala Harris'],
        'Win Percentage':[win_perc, 1-win_perc],
        'Date' : current_date,
        'LB' : [LB,(1-win_perc)-(win_perc-LB)],
        'UB' : [UB,(1-win_perc)+(UB-win_perc)]
    })

    tracking_data = tracking_data.query("Date != @current_date").reset_index(drop=True)

    tracking_data = pd.concat([tracking_data, new_row])

tracking_data = tracking_data.assign(Date = pd.to_datetime(tracking_data['Date']))

# Saving Data
prob_data.to_csv("./data/state_probabilities.csv", index = False)
sim_data.to_csv("./data/simulation_data.csv", index = False)
tracking_data.to_csv("./data/tracking_data.csv", index = False)
