import dash
import dash_cytoscape as cyto
import dash_html_components as html
from dash.dependencies import Input, Output
import networkx as nx

# Create a social graph
social_graph = nx.Graph()
social_graph.add_nodes_from(["Alice", "Bob", "Charlie", "David", "Eve"])
social_graph.add_edges_from([
    ("Alice", "Bob"),
    ("Bob", "Charlie"),
    ("Charlie", "David"),
    ("David", "Eve"),
    ("Eve", "Alice"),
])

# Create the Dash pyconlyse_control
app = dash.Dash(__name__)

# Define the layout
app.layout = html.Div([
    cyto.Cytoscape(
        id='social-graph',
        layout={'name': 'circle'},
        style={'width': '100%', 'height': '400px'},
        elements=[
            {'data': {'id': node, 'label': node}} for node in social_graph.nodes
        ] + [
            {'data': {'source': edge[0], 'target': edge[1]}} for edge in social_graph.edges
        ]
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
