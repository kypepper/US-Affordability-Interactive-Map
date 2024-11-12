import pandas as pd
import plotly.express as px
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

# State name to abbreviation mapping
state_mapping = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'
}

# Load data
income_df = pd.read_csv('household_income.csv')
expenses_df = pd.read_csv('living_expense.csv')
job_salaries_df = pd.read_csv('job_salaries.csv')
tax_df = pd.read_csv('tax_rates.csv')

# Convert monthly expenses to annual
expenses_df[['Grocery', 'Housing', 'Utilities', 'Transportation', 'Health', 'Misc.']] *= 12

# Add state abbreviation to the expenses data
expenses_df['Abbreviation'] = expenses_df['State'].map(state_mapping)

# Calculate the national average household income
national_avg_income = income_df[income_df['State'] == 'USA']['Household Income'].values[0]

# Remove the national average row for state-specific calculations
income_df = income_df[income_df['State'] != 'USA']

# Calculate percentage difference from national average for each state
income_df['Percentage Difference from National Average'] = (
    (income_df['Household Income'] - national_avg_income) / national_avg_income
) * 100

# Merge datasets
merged_df = pd.merge(income_df, expenses_df, on='State')
merged_df['Total Expenses'] = merged_df[['Grocery', 'Housing', 'Utilities', 'Transportation', 'Health', 'Misc.']].sum(axis=1)

# Merge tax data
tax_df.columns = tax_df.columns.str.strip()
merged_df = pd.merge(merged_df, tax_df[['State', 'State Tax Rate']], on='State', how='left')

# Convert tax rate to a float
merged_df['State Tax Rate'] = merged_df['State Tax Rate'].str.rstrip('%').astype('float') / 100

# Load and adjust job salaries
job_salaries_df.columns = job_salaries_df.columns.str.strip()
job_salaries_df['average_salary'] = job_salaries_df['average_salary'].astype(float)

# Create a placeholder DataFrame for merging
job_salaries_df['State'] = 'USA'
adjusted_salaries_df = pd.merge(job_salaries_df, income_df[['State', 'Percentage Difference from National Average']], on='State', how='left')

# Adjust the salaries based on the percentage difference
adjusted_salaries_df['Adjusted Salary'] = adjusted_salaries_df['average_salary'] * (1 + adjusted_salaries_df['Percentage Difference from National Average'] / 100)

# Initialize the Dash app
app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div([
        dcc.Dropdown(
            id='career-dropdown',
            options=[{'label': job, 'value': job} for job in job_salaries_df['Job'].unique()],
            value=job_salaries_df['Job'].unique()[0],
            placeholder="Select a career",
            style={'width': '230px', 'margin': '0 auto'}
        ),
        html.Div([
            dcc.Graph(id='top-bar-chart'),
            dcc.Graph(id='bottom-bar-chart')
        ], style={'display': 'flex', 'flex-direction': 'column', 'height': '600px', 'width': '100%'})
    ], style={'width': '37%', 'display': 'inline-block'}),

    html.Div([
        dcc.Graph(id='choropleth-map')
    ], style={'width': '100%', 'display': 'inline-block'}),

    html.Div(id='state-info')
], style={'display': 'flex', 'flex-direction': 'row'})


@app.callback(
    [Output('choropleth-map', 'figure'),
     Output('top-bar-chart', 'figure'),
     Output('bottom-bar-chart', 'figure'),
     Output('state-info', 'children')],
    [Input('career-dropdown', 'value'),
     Input('choropleth-map', 'clickData')]
)
def update_map_and_bars(selected_career, clickData):
    # Create a copy of merged_df for manipulation
    working_df = merged_df.copy()

    print(f"Selected Career: {selected_career}")

    if selected_career == "Average of all Occupations":
        avg_salary = job_salaries_df[job_salaries_df['Job'] == "Average of all Occupations"]['average_salary'].values[0]
        working_df['Adjusted Salary'] = avg_salary
        print(f"Avg Salary: {avg_salary}")
    else:
        # Filter job salary data based on selected career
        career_salary = job_salaries_df[job_salaries_df['Job'] == selected_career]
        print(f"Career Salary Data:\n{career_salary}")

        if career_salary.empty:
            print("No data available for this career.")
            return px.choropleth(), px.bar(), px.bar(), "No data available for this career."

        if 'State' in career_salary.columns and career_salary['State'].iloc[0] == 'USA':
            # Handling case when data is provided only as national average
            avg_salary = career_salary['average_salary'].iloc[0]
            # Calculate adjusted salaries for each state
            working_df['Adjusted Salary'] = avg_salary * (1 + working_df['Percentage Difference from National Average'] / 100)
        else:
            # Prepare career salary DataFrame with the correct state-wise salary
            career_salary = career_salary[['State', 'average_salary']]
            career_salary.rename(columns={'average_salary': 'Adjusted Salary'}, inplace=True)

            # Merge the career salary data with working_df
            working_df = pd.merge(working_df, career_salary, on='State', how='left')
        
        print(f"Working DataFrame after Merge:\n{working_df.head()}")

    # Calculate tax amount
    working_df['Tax Amount'] = working_df['Adjusted Salary'] * working_df['State Tax Rate']

    # Subtract tax amount from adjusted salary
    working_df['Adjusted Salary After Tax'] = working_df['Adjusted Salary'] - working_df['Tax Amount']

    # Calculate Income to Expenses Ratio
    working_df['Income to Expenses Ratio'] = working_df['Adjusted Salary After Tax'] / working_df['Total Expenses']
    print(f"Working DataFrame with Ratios:\n{working_df[['State', 'Income to Expenses Ratio']].head()}")

    # Handle cases where ratio is NaN
    min_ratio = working_df['Income to Expenses Ratio'].min()
    max_ratio = working_df['Income to Expenses Ratio'].max()
    if pd.isna(min_ratio) or pd.isna(max_ratio):
        min_ratio = 0
        max_ratio = 5

    # Define a detailed color scale with drastic changes
    fixed_color_scale = [
        [0, '#FF4136'],  
        [0.25, '#FFDC00'],  
        [0.5, '#FFD700'],  
        [0.75, '#2ECC40'],  
        [1, '#004D40']   
    ]

    # Create choropleth map
    fig_map = px.choropleth(working_df, 
                           locations='Abbreviation', 
                           locationmode='USA-states', 
                           color='Income to Expenses Ratio',
                           hover_name='State',
                           color_continuous_scale=fixed_color_scale,
                           range_color=[1, 5],
                           title=f'Affordability of Living Expenses vs. {selected_career} Salary by State',
                           labels={'Income to Expenses Ratio': 'Income to Expenses Ratio', 'State': 'State'},
                           scope='usa')

    fig_map.update_layout(
        coloraxis_colorbar=dict(
            title='Income to Expenses Ratio',
            tickvals=[1, 2, 3, 4, 5],
            ticktext=['1', '2', '3', '4', '5']
        ),
        height=600,  # Set your desired height
        width=1000    # Set your desired width
    )

    # Create top bar chart
    top_bar_chart = px.bar(working_df.sort_values(by='Income to Expenses Ratio', ascending=False).head(10),
                           x='State',
                           y='Income to Expenses Ratio',
                           title='Top 10 States by Income to Expenses Ratio',
                           color='Income to Expenses Ratio',
                           color_continuous_scale=fixed_color_scale,
                           range_color=[1, 5])
    top_bar_chart.update_layout(coloraxis_showscale=False)

    # Create bottom bar chart
    bottom_bar_chart = px.bar(working_df.sort_values(by='Income to Expenses Ratio', ascending=True).head(10),
                              x='State',
                              y='Income to Expenses Ratio',
                              title='Bottom 10 States by Income to Expenses Ratio',
                              color='Income to Expenses Ratio',
                              color_continuous_scale=fixed_color_scale,
                              range_color=[1, 5])
    bottom_bar_chart.update_layout(coloraxis_showscale=False)

    # Display state info if a state is clicked
    state_info = "Click on a state to see detailed information."
    if clickData:
        state_clicked = clickData['points'][0]['location']
        state_data = working_df[working_df['Abbreviation'] == state_clicked].iloc[0]
        state_info = (f"State: {state_data['State']}\n"
                      f"Household Income: ${state_data['Household Income']:,}\n"
                      f"Total Expenses: ${state_data['Total Expenses']:,}\n"
                      f"State Tax Rate: {state_data['State Tax Rate'] * 100:.2f}%\n"
                      f"Income to Expenses Ratio: {state_data['Income to Expenses Ratio']:.2f}")

    return fig_map, top_bar_chart, bottom_bar_chart, state_info

if __name__ == '__main__':
    app.run_server(debug=True)