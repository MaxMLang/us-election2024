import pandas as pd
import numpy as np
import pymc as pm
import arviz as az
from pytensor.printing import Print

def load_polling_data():

    link_538 = 'https://projects.fivethirtyeight.com/polls/data/president_polls.csv'

    data = pd.read_csv(link_538)

    # Collapsing `methodology` variable
    panels_to_keep = [
        'Online Panel', 
        'Live Phone',
        'Probability Panel',
        'App Panel'
    ]

    data.loc[
        (~data.methodology.isin(panels_to_keep)), 'methodology'
    ] = 'Other'

    # Collapsing `population` variable
    data.population = data.population.replace({'v':'a'})

    # Adding a partisan variable
    data['rep_poll'] = np.where(data['partisan'] == 'REP', 1, 0)

    #filter out where state is NA
    data = data.loc[~data.state.isna(),:].reset_index(drop=True)

    def identify_multi_candidate(data):
        #identify multi response questions
        if data.shape[0] > 2:
            data['MultiCandidate'] = 1
        elif data.shape[0] == 2:
            data['MultiCandidate'] = 0
        else:
            print(data)
            raise Exception("Something weird going on")
        #identify non biden v trump questions
        candidate_ids = [16661,16651]
        keep = set(data['candidate_id'].to_list()) \
            .intersection(set(candidate_ids))
        keep = int(len(keep)>1)
        data['candidate_vs'] = keep
        return data

    def rescale_to_100(data):
        data.pct = np.divide(data.pct,data.pct.sum())
        return data

    cols_to_keep = [
        'methodology',
        'rep_poll',
        'population',
        'state',
        'sample_size',
        'MultiCandidate',
        'end_date',
        'numeric_grade',
        'pct'
    ]

    data = (
        data
            .groupby("question_id")
            .apply(identify_multi_candidate)
            .reset_index(drop=True)
            .query('candidate_vs == 1')
            .drop(columns = ['candidate_vs'])
            .reset_index(drop=True)
            .query('candidate_id == 16661 or candidate_id == 16651')
            .groupby("question_id")
            .apply(rescale_to_100)
            .reset_index(drop=True)
            .query("candidate_id == 16651")
            [cols_to_keep]
    )

    # There are missing grades, so need to impute
    data.numeric_grade = data.numeric_grade.fillna(data.numeric_grade.median())

    data = (
        data
            .assign(
                date_maker = pd.to_datetime(data.end_date),
                month2 = lambda x:x.date_maker.dt.month,
                year = lambda x:x.date_maker.dt.year - 2021,
                date_maker2 = lambda x:x.month2 + x.year*12,
                month = lambda x:x.date_maker2 - x.date_maker2.min()
            )
            .drop(
                columns = [
                    'date_maker',
                    'date_maker2',
                    'month2',
                    'year',
                    'end_date'
                ]
            )
    )
    
    data.state = data.state.replace({
        'Nebraska CD-1':'NE-1',
        'Nebraska CD-2':'NE-2',
        'Nebraska CD-3':'NE-3',
        'Maine CD-1':'ME-1',
        'Maine CD-2':'ME-2',
    })
    
    states = data.state.value_counts().index.to_list()
    states_dict = {x:i for i,x in enumerate(states)}
    data.state = data.state.replace(states_dict)
    
    method = pd.get_dummies(data.methodology) \
        .drop(columns = ['Probability Panel']) \
        .astype('int')
    
    population = pd.get_dummies(data.population) \
        .drop(columns = ['a']) \
        .astype('int')
    
    data['grade'] = (data.numeric_grade >= 2).astype("int")
    
    data.drop(columns = ['methodology', 'population', 'numeric_grade'], inplace = True)
    
    data = pd.concat([data,method,population], axis=1)

    cols_to_iterate = [x for x in data.columns if 'pct' != x]
    for col in cols_to_iterate:
        data[col] = data[col].fillna(data[col].mean())

    data.dropna(subset = ['pct'], inplace=True)
    
    return data['pct'].values, \
        data, \
        states_dict

def load_priors(var, metric, priors):
    return priors.query("var == @var")[metric].iloc[0]

def simulate_election_states(model, states_dict, x_matrix, trace):
    with model:
        pm.set_data({
            "X1": [0 for x in range(len(states_dict))],
            "X2": [1 for x in range(len(states_dict))],
            "X3": [0 for x in range(len(states_dict))],
            "X4": [x_matrix['month'].max() for x in range(len(states_dict))],
            "X5": [1 for x in range(len(states_dict))],
            "X6": [2000 for x in range(len(states_dict))],
            "X7": [1 for x in range(len(states_dict))],
            "X8": [1 for x in range(len(states_dict))],
            "X9": [0 for x in range(len(states_dict))],
            "X10": [1 for x in range(len(states_dict))],
            'Y_obs': [-1000 for x in range(len(states_dict))],
            'states': list(states_dict.values())
        })
        pp = pm.sample_posterior_predictive(
            trace, predictions=True, random_seed=1
        )

        pred_matrix = pp['predictions']['y'].mean(('chain'))

        results = {}

        for i in range(pred_matrix.shape[1]):
            val = np.divide(np.sum(np.greater(pred_matrix[:,i],0.5)),len(pred_matrix[:,1]))
            val = round(float(val)*100,2)
            results[list(states_dict.keys())[i]] = val  
        
        # Add in states not in polling dataset
        file_url = 'https://projects.fivethirtyeight.com/2020-general-data/presidential_poll_averages_2020.csv'

        old_data = pd.read_csv(file_url).query("candidate_name == 'Donald Trump' and modeldate == '11/3/2020'")[['state', 'pct_estimate']] \
            .assign(pct_estimate = lambda x:np.where(x.pct_estimate>50,99,1))
        
        old_data = pd.concat([old_data,pd.DataFrame({'state':"NE-3", 'pct_estimate':99}, index=[0])])

        states_to_drop = list(results.keys())

        old_data = old_data.loc[~old_data.state.isin(states_to_drop),:]
        
        for i,row in old_data.iterrows():
            results[row.iloc[0]] = row.iloc[1]
        
        return {k:v for k,v in results.items() if k != 'National'}

def fit_bhm(y_vec, x_matrix, state_dict):
    n_state = len(state_dict)
    state_r = x_matrix.state.values

    with pm.Model() as model:

        # b0 - intercept 
        mu_b0 = pm.Normal('mu_b0', 0, sigma=1)
        sigma_b0 = pm.HalfCauchy('sigma_b0', 5)
        
        # Random intercepts as offsets
        a_offset = pm.Normal('a_offset', mu=0, sigma=1, shape=n_state)
        b0 = pm.Deterministic("Intercept", mu_b0 + a_offset * sigma_b0)

        # Setting data
        X1 = pm.MutableData("X1", x_matrix['Live Phone'].values)
        X2 = pm.MutableData("X2", x_matrix['Online Panel'].values)
        X3 = pm.MutableData("X3", x_matrix['Other'].values)
        X4 = pm.MutableData("X4", x_matrix['month'].values)
        X5 = pm.MutableData("X5", x_matrix['rep_poll'].values)
        X6 = pm.MutableData("X6", x_matrix['sample_size'].values)
        X7 = pm.MutableData("X7", x_matrix['MultiCandidate'].values)
        X8 = pm.MutableData("X8", x_matrix['lv'].values)
        X9 = pm.MutableData("X9", x_matrix['rv'].values)
        X10 = pm.MutableData("X10", x_matrix['grade'].values)
        Y_obs = pm.MutableData("Y_obs", y_vec)
        states = pm.MutableData("states", state_r)

        b1 = pm.Normal("Live Phone", mu=0, sigma=0.1)
        b2 = pm.Normal("Online Panel", mu=0, sigma=0.1)
        b3 = pm.Normal("Other", mu=0, sigma=0.1)
        b4 = pm.Normal("month", mu=0, sigma=0.1)
        b5 = pm.Normal("rep_poll", mu=0, sigma=1)
        b6 = pm.Normal("sample_size", mu=0, sigma=1)
        b7 = pm.Normal("MultiCandidate", mu=0, sigma=1)
        b8 = pm.Normal("lv", mu=0, sigma=1)
        b9 = pm.Normal("rv", mu=0, sigma=1)
        b10 = pm.Normal("grade", mu=0, sigma=1)

        formula =  (
            b0[states] + 
            b1*X1 + 
            b2*X2 + 
            b3*X3 + 
            b4*X4 + 
            b5*X5 +
            b6*X6 +
            b7*X7 +
            b8*X8 +
            b9*X9 +
            b10*X10
        )
        
        s = pm.HalfNormal('error',sigma =1)

        obs = pm.Normal('y', mu = formula, sigma=s, observed=Y_obs)

        trace = pm.sample(1000, tune=1000, cores=1)

        return model, trace
    
def fit_bhm_custom_belief(y_vec, x_matrix, state_dict, priors):
    n_state = len(state_dict)
    state_r = x_matrix.state.values

    with pm.Model() as model:

        # b0 - intercept 
        mu_b0 = pm.Normal(
            'mu_b0', 
            load_priors('mu_b0', 'mean', priors),
            sigma=load_priors('mu_b0', 'sd', priors))
        sigma_b0 = pm.HalfCauchy('sigma_b0', load_priors('sigma_b0', 'mean', priors))
        
        # Random intercepts as offsets
        mns = []
        sds = []
        
        for state,num in state_dict.items():
            if not priors.query('state == @state').empty:
                mn = priors.query('state == @state')['mean'].iloc[0]
                sd = priors.query('state == @state')['sd'].iloc[0]
            else:
                mn = 0,
                sd = 1
            mns.append(mn)
            sds.append(sd)
        
        a_offset = pm.Normal('a_offset', mu=mns, sigma=sds, shape=n_state)
        b0 = pm.Deterministic("Intercept", mu_b0 + a_offset * sigma_b0)

        # Setting data
        X1 = pm.MutableData("X1", x_matrix['Live Phone'].values)
        X2 = pm.MutableData("X2", x_matrix['Online Panel'].values)
        X3 = pm.MutableData("X3", x_matrix['Other'].values)
        X4 = pm.MutableData("X4", x_matrix['month'].values)
        X5 = pm.MutableData("X5", x_matrix['rep_poll'].values)
        X6 = pm.MutableData("X6", x_matrix['sample_size'].values)
        X7 = pm.MutableData("X7", x_matrix['MultiCandidate'].values)
        X8 = pm.MutableData("X8", x_matrix['lv'].values)
        X9 = pm.MutableData("X9", x_matrix['rv'].values)
        X10 = pm.MutableData("X10", x_matrix['grade'].values)
        Y_obs = pm.MutableData("Y_obs", y_vec)
        states = pm.MutableData("states", state_r)

        b1 = pm.Normal("Live Phone", mu=load_priors('Live Phone', 'mean', priors), sigma=load_priors('Live Phone', 'sd', priors))
        b2 = pm.Normal("Online Panel", mu=load_priors('Online Panel', 'mean', priors), sigma=load_priors('Online Panel', 'sd', priors))
        b3 = pm.Normal("Other", mu=load_priors('Other', 'mean', priors), sigma=load_priors('Other', 'sd', priors))
        b4 = pm.Normal("month", mu=load_priors('month', 'mean', priors), sigma=load_priors('month', 'sd', priors))
        b5 = pm.Normal("rep_poll", mu=load_priors('rep_poll', 'mean', priors), sigma=load_priors('rep_poll', 'sd', priors))
        b6 = pm.Normal("sample_size", mu=load_priors('sample_size', 'mean', priors), sigma=load_priors('sample_size', 'sd', priors))
        b7 = pm.Normal("MultiCandidate", mu=load_priors('MultiCandidate', 'mean', priors), sigma=load_priors('MultiCandidate', 'sd', priors))
        b8 = pm.Normal("lv", mu=load_priors('lv', 'mean', priors), sigma=load_priors('lv', 'sd', priors))
        b9 = pm.Normal("rv", mu=load_priors('rv', 'mean', priors), sigma=load_priors('rv', 'sd', priors))
        b10 = pm.Normal("grade", mu=load_priors('grade', 'mean', priors), sigma=load_priors('grade', 'sd', priors))

        formula =  (
            b0[states] + 
            b1*X1 + 
            b2*X2 + 
            b3*X3 + 
            b4*X4 + 
            b5*X5 +
            b6*X6 +
            b7*X7 +
            b8*X8 +
            b9*X9 +
            b10*X10
        )
        
        s = pm.HalfNormal('error', sigma =load_priors('error', 'mean', priors))

        obs = pm.Normal('y', mu = formula, sigma=s, observed=Y_obs)

        trace = pm.sample(1000, tune=1000, cores=1)

        return model, trace

def simulate_election(preds, simulation_num):
    '''
    given a dict with each state's probability of one candidate winning
    will return number of simulations won by that candidate
    '''
    import numpy as np
    import pandas as pd
    
    ec_data = {'Arizona': 11,
    'Georgia': 16,
    'Pennsylvania': 19,
    'Michigan': 15,
    'Nevada': 6,
    'Wisconsin': 10,
    'North Carolina': 3,
    'Ohio': 17,
    'Florida': 30,
    'New Hampshire': 4,
    'New York': 28,
    'California': 54,
    'Iowa': 6,
    'Tennessee': 11,
    'Virginia': 13,
    'Missouri': 10,
    'Texas': 40,
    'Colorado': 10,
    'Montana': 4,
    'Washington': 12,
    'Illinois': 19,
    'Connecticut': 7,
    'Oklahoma': 7,
    'New Mexico': 5,
    'Kansas': 6,
    'Massachusetts': 11,
    'Minnesota': 10,
    'Kentucky': 8,
    'Alaska': 3,
    'Oregon': 8,
    'Nebraska': 2,
    'South Carolina': 9,
    'Maryland': 10,
    'Rhode Island': 4,
    'Arkansas': 6,
    'South Dakota': 3,
    'Louisiana': 8,
    'Mississippi': 6,
    'Maine': 2,
    'Utah': 6,
    'Idaho': 4,
    'Alabama': 9,
    'West Virginia': 4,
    'Indiana': 11,
    'North Dakota': 3,
    'Wyoming': 3,
    'Vermont': 3,
    'New Jersey': 14,
    'National': 1,
    'NE-1': 1,
    'NE-2': 1,
    'NE-3':1,
    'ME-2': 1,
    'ME-1': 1,
    'Hawaii': 4,
    'District of Columbia': 3,
    'Delaware': 3}
    
    def simulate_state(prob, points):
        prob = prob/100
        trump_win = np.random.choice([0,1], p=[1-prob, prob])
        return trump_win*points
    
    winner = []
    points = []
    sim_num = []
    
    for _ in range(simulation_num):
        votes = [simulate_state(prob,ec_data[state]) for state,prob in preds.items()]
        tot_votes = sum(votes)
        winner.append(np.where(tot_votes>=270, 1,0))
        points.append(tot_votes)
    
    data = pd.DataFrame({
        'winner':winner,
        'points':points
    })
    
    trump_won = sum(data.winner)/data.shape[0]
    
    return trump_won, data

def get_credible_interval(sim_data:pd.DataFrame, conf_level:int=95):
    '''
    Sample from the 50,000 daily simulations finding the upper and lower bounds given percentile(conf_level)
    '''
    assert conf_level > 0 and conf_level < 100
    conf_data = [sum(sim_data.winner.sample(n=100) == "Trump")/100 for x in range(1000)]
    conf_data = np.array(conf_data)
    s = (100 - conf_level)/2
    UB = 100 - s
    LB = s
    res = np.percentile(conf_data, [LB, UB])
    return res[0], res[1]

def update_priors(trace, state_dict):
    priors = az.summary(trace, kind="stats", var_names=['~Intercept']) \
        .reset_index() \
        .rename(columns = {'index':'var'}) \
        [['var', 'mean', 'sd']]
    states_df = pd.DataFrame({
        'state' : list(state_dict.keys()),
        'var' : [f'a_offset[{x}]' for x in list(state_dict.values())]
    })
    priors = priors.merge(states_df, how='left', on='var')
    priors = priors.assign(
        sd = lambda x:np.where(x.sd<=0, 0.01, x.sd)
    )
    priors.to_csv('./data/priors.csv', index=False)

def update_custom_priors(y_vec, x_matrix, state_dict, priors):
    n_state = len(state_dict)
    state_r = x_matrix.state.values

    with pm.Model() as model:
        
        #hyperpriors for intercepts
        mu_b0 = pm.Normal(
            'mu_b0', 
            load_priors('mu_b0', 'mean', priors),
            sigma=load_priors('mu_b0', 'sd', priors))
        sigma_b0 = pm.HalfCauchy('sigma_b0', load_priors('sigma_b0', 'mean', priors))
        
        # Random intercepts as offsets
        mns = []
        sds = []
        
        for state,num in state_dict.items():
            if not priors.query('state == @state').empty:
                mn = priors.query('state == @state')['mean'].iloc[0]
                sd = priors.query('state == @state')['sd'].iloc[0]
            else:
                mn = 0,
                sd = 1
            mns.append(mn)
            sds.append(sd)
        
        a_offset = pm.Normal('a_offset', mu=0, sigma=10, shape=n_state)
        b0 = pm.Deterministic("Intercept", mu_b0 + a_offset*sigma_b0)

        # Setting data
        X1 = pm.MutableData("X1", x_matrix['Live Phone'].values)
        X2 = pm.MutableData("X2", x_matrix['Online Panel'].values)
        X3 = pm.MutableData("X3", x_matrix['Other'].values)
        X4 = pm.MutableData("X4", x_matrix['month'].values)
        X5 = pm.MutableData("X5", x_matrix['rep_poll'].values)
        X6 = pm.MutableData("X6", x_matrix['sample_size'].values)
        X7 = pm.MutableData("X7", x_matrix['MultiCandidate'].values)
        X8 = pm.MutableData("X8", x_matrix['lv'].values)
        X9 = pm.MutableData("X9", x_matrix['rv'].values)
        X10 = pm.MutableData("X10", x_matrix['grade'].values)
        Y_obs = pm.MutableData("Y_obs", y_vec)
        states = pm.MutableData("states", state_r)

        b1 = pm.Normal("Live Phone", mu=load_priors('Live Phone', 'mean', priors), sigma=load_priors('Live Phone', 'sd', priors))
        b2 = pm.Normal("Online Panel", mu=load_priors('Online Panel', 'mean', priors), sigma=load_priors('Online Panel', 'sd', priors))
        b3 = pm.Normal("Other", mu=load_priors('Other', 'mean', priors), sigma=load_priors('Other', 'sd', priors))
        b4 = pm.Normal("month", mu=load_priors('month', 'mean', priors), sigma=load_priors('month', 'sd', priors))
        b5 = pm.Normal("rep_poll", mu=load_priors('rep_poll', 'mean', priors), sigma=load_priors('rep_poll', 'sd', priors))
        b6 = pm.Normal("sample_size", mu=load_priors('sample_size', 'mean', priors), sigma=load_priors('sample_size', 'sd', priors))
        b7 = pm.Normal("MultiCandidate", mu=load_priors('MultiCandidate', 'mean', priors), sigma=load_priors('MultiCandidate', 'sd', priors))
        b8 = pm.Normal("lv", mu=load_priors('lv', 'mean', priors), sigma=load_priors('lv', 'sd', priors))
        b9 = pm.Normal("rv", mu=load_priors('rv', 'mean', priors), sigma=load_priors('rv', 'sd', priors))
        b10 = pm.Normal("grade", mu=load_priors('grade', 'mean', priors), sigma=load_priors('grade', 'sd', priors))

        Mu =  pm.invlogit(
            b0[states] + 
            b1*X1 + 
            b2*X2 + 
            b3*X3 + 
            b4*X4 +
            b5*X5 +
            b6*X6 +
            b7*X7 +
            b8*X8 +
            b9*X9 +
            b10*X10
        )

        Phi = pm.Normal('phi', 100)
        
        A = pm.Deterministic('A', pm.math.switch(Mu*Phi <= 0, -np.inf, Mu*Phi))
        B = pm.Deterministic('B', pm.math.switch(Phi-A <= 0, -np.inf, Phi-A))
        
        obs = pm.Beta('y', alpha = A, beta = B,observed=Y_obs)

        trace = pm.sample(1000, tune=1000, cores=1, init = 'adapt_diag', target_accept = 0.9) #,  

        return model, trace

def fit_bayes_beta(y_vec, x_matrix, state_dict):
    n_state = len(state_dict)
    state_r = x_matrix.state.values
    
    sgma = 0.01

    with pm.Model() as model:
        
        sgma = 20
        
        # Random intercepts as offsets
        mu_b0 = pm.Normal('mu_b0', 0, sigma=1)
        sigma_b0 = pm.HalfCauchy('sigma_b0', 1)
        a_offset = pm.Normal('a_offset', mu=0, sigma=10, shape=n_state)
        b0 = pm.Deterministic("Intercept", mu_b0 + a_offset*sigma_b0)

        # Setting data
        X1 = pm.MutableData("X1", x_matrix['Live Phone'].values)
        X2 = pm.MutableData("X2", x_matrix['Online Panel'].values)
        X3 = pm.MutableData("X3", x_matrix['Other'].values)
        X4 = pm.MutableData("X4", x_matrix['month'].values)
        X5 = pm.MutableData("X5", x_matrix['rep_poll'].values)
        X6 = pm.MutableData("X6", x_matrix['sample_size'].values)
        X7 = pm.MutableData("X7", x_matrix['MultiCandidate'].values)
        X8 = pm.MutableData("X8", x_matrix['lv'].values)
        X9 = pm.MutableData("X9", x_matrix['rv'].values)
        X10 = pm.MutableData("X10", x_matrix['grade'].values)
        Y_obs = pm.MutableData("Y_obs", y_vec)
        states = pm.MutableData("states", state_r)

        b1 = pm.Normal("Live Phone", mu=0, sigma=sgma)
        b2 = pm.Normal("Online Panel", mu=0, sigma=sgma)
        b3 = pm.Normal("Other", mu=0, sigma=sgma)
        b4 = pm.Normal("month", mu=0, sigma=0.1)
        b5 = pm.Normal("rep_poll", mu=0, sigma=sgma)
        b6 = pm.Normal("sample_size", mu=0, sigma=10)
        b7 = pm.Normal("MultiCandidate", mu=0, sigma=sgma)
        b8 = pm.Normal("lv", mu=0, sigma=sgma)
        b9 = pm.Normal("rv", mu=0, sigma=sgma)
        b10 = pm.Normal("grade", mu=0, sigma=sgma)

        Mu =  pm.invlogit(
            b0[states] + 
            b1*X1 + 
            b2*X2 + 
            b3*X3 + 
            b4*X4 +
            b5*X5 +
            b6*X6 +
            b7*X7 +
            b8*X8 +
            b9*X9 +
            b10*X10
        )

        Phi = pm.Normal('phi', 100)
        
        A = pm.Deterministic('A', pm.math.switch(Mu*Phi <= 0, -np.inf, Mu*Phi))
        B = pm.Deterministic('B', pm.math.switch(Phi-A <= 0, -np.inf, Phi-A))
        
        obs = pm.Beta('y', alpha = A, beta = B,observed=Y_obs)

        trace = pm.sample(1000, tune=1000, cores=1, init = 'adapt_diag', target_accept = 0.9) #,  

        return model, trace

def fit_bayes_beta_custom(y_vec, x_matrix, state_dict):
    n_state = len(state_dict)
    state_r = x_matrix.state.values
    
    sgma = 0.01

    with pm.Model() as model:
        
        sgma = 1
        
        # Random intercepts as offsets
        mu_b0 = pm.Normal('mu_b0', 0, sigma=1)
        sigma_b0 = pm.HalfCauchy('sigma_b0', 1)
        
        # Random intercepts as offsets
        a_offset = pm.Normal('a_offset', mu=0, sigma=10, shape=n_state)
        b0 = pm.Deterministic("Intercept", mu_b0 + a_offset*sigma_b0)

        # Setting data
        X1 = pm.MutableData("X1", x_matrix['Live Phone'].values)
        X2 = pm.MutableData("X2", x_matrix['Online Panel'].values)
        X3 = pm.MutableData("X3", x_matrix['Other'].values)
        X4 = pm.MutableData("X4", x_matrix['month'].values)
        X5 = pm.MutableData("X5", x_matrix['rep_poll'].values)
        X6 = pm.MutableData("X6", x_matrix['sample_size'].values)
        X7 = pm.MutableData("X7", x_matrix['MultiCandidate'].values)
        X8 = pm.MutableData("X8", x_matrix['lv'].values)
        X9 = pm.MutableData("X9", x_matrix['rv'].values)
        X10 = pm.MutableData("X10", x_matrix['grade'].values)
        Y_obs = pm.MutableData("Y_obs", y_vec)
        states = pm.MutableData("states", state_r)

        b1 = pm.Normal("Live Phone", mu=0, sigma=sgma)
        b2 = pm.Normal("Online Panel", mu=0, sigma=sgma)
        b3 = pm.Normal("Other", mu=0, sigma=sgma)
        b4 = pm.Normal("month", mu=0, sigma=0.1)
        b5 = pm.Normal("rep_poll", mu=0, sigma=sgma)
        b6 = pm.Normal("sample_size", mu=0, sigma=10)
        b7 = pm.Normal("MultiCandidate", mu=0, sigma=sgma)
        b8 = pm.Normal("lv", mu=0, sigma=sgma)
        b9 = pm.Normal("rv", mu=0, sigma=sgma)
        b10 = pm.Normal("grade", mu=0, sigma=sgma)

        Mu =  pm.invlogit(
            b0[states] + 
            b1*X1 + 
            b2*X2 + 
            b3*X3 + 
            b4*X4 +
            b5*X5 +
            b6*X6 +
            b7*X7 +
            b8*X8 +
            b9*X9 +
            b10*X10
        )

        sd = pm.HalfNormal('sd', sigma = 35)
        Phi = ((Mu * (1 - Mu)) / (sd**2 - 1))
        
        A = Mu*Phi
        B = Phi-A
        
        obs = pm.Beta('y', alpha = A, beta = B,observed=Y_obs)

        trace = pm.sample(1000, tune=1000, cores=1, init = 'adapt_diag', target_accept = 0.9) #,  

        return model, trace
