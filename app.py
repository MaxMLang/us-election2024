import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.express as px
import datetime
import plotly.graph_objects as go

# Load the data
simulation_data = pd.read_csv('./data/simulation_data.csv')
tracking_data = pd.read_csv('./data/tracking_data.csv')
state_probabilities = pd.read_csv('./data/state_probabilities.csv')

# Set up the Dash app and include Bootstrap for better styling
app = dash.Dash(__name__,
                external_stylesheets=['https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'],
                suppress_callback_exceptions=True)


# Navbar for navigation between pages
navbar = html.Nav([
    html.Ul([
        html.Li(html.A("Home", href="/", className="nav-link")),
        html.Li(html.A("Methodology", href="/methodology", className="nav-link")),
    ], className="nav navbar-nav")
], className="navbar navbar-expand-lg navbar-light bg-light")

# Days until the election (assuming it's November 5, 2024)
election_date = datetime.datetime(2024, 11, 5)
days_until_election = (election_date - datetime.datetime.now()).days

# Calculate the projected winner dynamically
def calculate_projected_winner(simulation_data):
    winner_counts = simulation_data['winner'].value_counts()
    projected_winner = winner_counts.idxmax()  # Get the candidate with the most wins
    return projected_winner

# Layout for the home page
home_layout = html.Div([
    navbar,
    # Header section with title and GitHub link
    html.Div([
        html.H1("US Presidential Election Dashboard 2024", className='display-4',
                style={'text-align': 'center', 'padding-top': '20px'}),
        html.Div([
            html.A(html.Img(src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
                            style={'height': '30px', 'margin-right': '10px'}),
                   href="https://github.com/MaxMLang", target="_blank"),
            html.Span("MaxMLang", style={'font-size': '20px'})
        ], style={'text-align': 'center', 'padding-bottom': '20px'}),
        html.P("This dashboard provides a real-time prediction of the 2024 US Presidential Election, "
               "based on various models and data sources. Navigate to the Methodology page to see "
               "how the predictions are generated.", style={'text-align': 'center'}),
        html.Hr(),
    ], className="jumbotron"),

    # Dashboard layout with cards for projected winner, simulations won, and days until election
    html.Div([
        html.Div([
            html.Div([
                html.H4("Projected Winner", className='card-title'),
                html.H2(id='projected-winner', className='card-text', style={'font-weight': 'bold'})
            ], className="card-body", style={'background-color': '#f5f5f5', 'border-radius': '10px'})  # Smoking white
        ], className="card text-dark mb-3", style={'max-width': '18rem'}),  # Dark text for smoking white background

        html.Div([
            html.Div([
                html.H4("Simulations Won Today", className='card-title'),
                html.H3(f"{tracking_data['Win Percentage'].iloc[-1]:.2f}%", className='card-text',
                        style={'font-weight': 'bold'})
            ], className="card-body", style={'background-color': '#f5f5f5', 'border-radius': '10px'})  # Smoking white
        ], className="card text-dark mb-3", style={'max-width': '18rem'}),  # Uniform color and smoking white

        html.Div([
            html.Div([
                html.H4("Days Until Election", className='card-title'),
                html.H3(f"{days_until_election}", className='card-text', style={'font-weight': 'bold'})
            ], className="card-body", style={'background-color': '#f5f5f5', 'border-radius': '10px'})  # Smoking white
        ], className="card text-dark mb-3", style={'max-width': '18rem'}),  # Uniform color and smoking white
    ], className="d-flex justify-content-around mb-4", style={'padding': '20px'}),

    # Graphs: Map, Simulations over time, and Electoral College vote distribution
    html.Div([
        dcc.Graph(id='state-map', figure={}),
        dcc.Graph(id='simulations-over-time', figure={}),
        dcc.Graph(id='vote-distribution', figure={}),  # Distribution plot added
    ], className="container")
])

# Methodology page layout
methodology_layout = html.Div([
    navbar,
    html.H1("2024 Election Model Methodology", className='display-4', style={'text-align': 'center', 'padding-top': '20px'}),
    html.Div([
        html.P(
            "The election model presented here employs a Hierarchical Bayesian Regression framework to forecast the "
            "outcome of the 2024 U.S. Presidential Election. This advanced approach was selected to address limitations "
            "in simpler statistical models to accommodate for state-level data in a "
            "U.S. election context. By introducing a hierarchical structure and employing Beta regression, we can simulate the US election an unlimited number of times based on past polling data."
            "A key question, nevertheless, how do you weigh your polling data (prior information)? Back in 2016 that went horribly wrong and led to models which were far off the actual result. Keep in mind, this could always happen again. All models are wrong, some are useful."
            ,
            style={'padding': '20px'}
        ),
        html.P("The methodology can be summarized as follows:", style={'padding': '20px'}),
        html.Ul([
            html.Li("Hierarchical Bayesian Model with state-level intercepts to account for state-specific variability (one could also try out a county intercept nested within the states)"),
            html.Li("Beta regression to handle bounded predictions between 0% and 100%"),
            html.Li("Control variables include pollster effects, survey mode, voter population (e.g., likely voters, registered voters, etc.)"),
            html.Li("Filtering based on poll quality, such as excluding polls below C+ rating based on FiveThirtyEight's grading system"),
        ], style={'padding-left': '40px'}),
        html.P(
            "Weaknesses of this model include the potential for relying too heavily on polling data (prior information) which might not grasp other effects and therefore could overly influence predictions over time, "
            "Furthermore, beta regression, "
            "while useful for bounded outcomes, may struggle with extreme values close to 0% or 100%, where it tends to produce "
            "less reliable predictions. Additionally, the reliance on quality polls means that in states where few high-quality "
            "polls exist, the model may produce less reliable results.",
            style={'padding': '20px'}
        ),
    ])
])

# Define callback to switch between home and methodology pages
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')]
)
def display_page(pathname):
    if pathname == '/methodology':
        return methodology_layout
    else:
        return home_layout

# Main app layout with URL routing
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# Callbacks for updating the map, time series chart, and vote distribution chart
@app.callback(
    [Output('state-map', 'figure'),
     Output('simulations-over-time', 'figure'),
     Output('vote-distribution', 'figure'),
     Output('projected-winner', 'children')],
    Input('state-map', 'id')
)
def update_dashboard(_):
    import plotly.graph_objects as go

    # Convert percentages to probabilities (scale from 0-1)
    state_probabilities['Trump Win Prob.'] = state_probabilities['Trump Win Prob.'] / 100
    state_probabilities['Harris Win Prob.'] = 1 - state_probabilities['Trump Win Prob.']

    # Format the hover text to show percentages with two decimals
    state_probabilities['hover_text'] = state_probabilities.apply(
        lambda row: f"Trump: {row['Trump Win Prob.']:.2%}, Harris: {row['Harris Win Prob.']:.2%}", axis=1)

    # Create the custom choropleth map using go.Choropleth
    fig_map = go.Figure(go.Choropleth(
        locations=state_probabilities['State'],
        locationmode="USA-states",
        z=state_probabilities['Trump Win Prob.'],  # This is used for hover data, but won't affect the color
        text=state_probabilities['hover_text'],  # Corrected hover text to show percentages
        hoverinfo="text",  # Display custom hover text
        marker=dict(line=dict(color='white', width=0.5)),
        colorscale=[[0, 'rgba(0,0,255,1)'], [1, 'rgba(255,0,0,1)']],  # Custom red-blue color scale
        colorbar=dict(title="Win Probability", ticksuffix="%"),
        showscale=False  # Hide the color scale legend
    ))

    # Update the layout for the map
    fig_map.update_layout(
        title_text="Win Probability by State (Red for Trump, Blue for Harris)",
        geo=dict(
            scope='usa',
            projection=go.layout.geo.Projection(type='albers usa'),
            showlakes=True,  # Add lakes
            lakecolor='rgb(255, 255, 255)'
        )
    )

    fig_map.update_traces(marker_line_width=0.5, marker_line_color="white")

    # Filter data for each candidate
    trump_data = tracking_data[tracking_data['Candidate'] == 'Trump']
    harris_data = tracking_data[tracking_data['Candidate'] == 'Harris']

    # Time Series for both candidates
    fig_time_series = px.line(
        tracking_data,
        x='Date',
        y='Win Percentage',
        color='Candidate',
        title="Simulations Won Over Time",
        labels={"Win Percentage": "Percentage"},
        template="plotly_white"
    )

    # Adding confidence intervals
    fig_time_series.add_scatter(x=trump_data['Date'], y=trump_data['LB'], mode='lines',
                                line=dict(width=0), showlegend=False, name='Trump LB')
    fig_time_series.add_scatter(x=trump_data['Date'], y=trump_data['UB'], mode='lines',
                                fill='tonexty', line=dict(width=0), showlegend=False, name='Trump UB')

    fig_time_series.add_scatter(x=harris_data['Date'], y=harris_data['LB'], mode='lines',
                                line=dict(width=0), showlegend=False, name='Harris LB')
    fig_time_series.add_scatter(x=harris_data['Date'], y=harris_data['UB'], mode='lines',
                                fill='tonexty', line=dict(width=0), showlegend=False, name='Harris UB')

    # Distribution of Electoral Votes (Trump vs Harris)
    fig_distribution = px.histogram(
        simulation_data,
        x='points',
        color='winner',
        nbins=50,
        title="Today's Simulations Won by Candidate",
        labels={"points": "EC Votes (Trump Wins)"},
        template="plotly_white"
    )

    # Calculate projected winner
    projected_winner = calculate_projected_winner(simulation_data)

    return fig_map, fig_time_series, fig_distribution, projected_winner



if __name__ == '__main__':
    app.run_server(debug=True)

