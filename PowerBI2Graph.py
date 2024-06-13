import zipfile
import json
import re
from os.path import exists
import networkx as nx
import matplotlib.pyplot as plt
import sys
from antlr4 import * 
from lexer.PowerQueryLexer import PowerQueryLexer

def get_model_edges(model: dict, nodes: dict) -> list[tuple]:
    """
        Gets all the edges of the model.
        Returns a list of tuple representig the edges.
        For example : [(A, B), (B, C)]
    """
    tables = model["model"]["tables"]
    edges = get_edges_from_tables(nodes, tables)
    if "expressions" in model["model"]:
        expressions = tables = model["model"]["expressions"]
        edges += get_edges_from_expressions(nodes, expressions)
         
    return edges

def get_model_nodes(model: dict) -> list:
    """
        Gets the name of all the tables in the mode
    """
    tables = model["model"]["tables"]
    table_names = [table["name"] for table in tables]

    expressions_names = []
    if "expressions" in model["model"]:
        expressions = model["model"]["expressions"]
        expressions_names = [expression["name"] for expression in expressions]
    
    return list(set(table_names + expressions_names))

def extract_model_file(filename: str, output_folder: str):
    """
        Extracts the DataModelSchema off of the ".pbit" file 
    """
    assert filename.endswith(".pbit"), "This function takes the model of a powerbi dashboard in input. It is a file with the 'pbit' extension"
    with zipfile.ZipFile(filename, 'r') as zip:
        zip.extract("DataModelSchema", output_folder)

def read_model_file(filename: str, temp_storage= "temp") -> dict:
    """
        Reads the model schema from the ".pbit" model file
        Returns the model in a json format
    """
    extract_model_file(filename, temp_storage)
    assert exists(f"{temp_storage}/DataModelSchema"), "There is no DataModelSchema in the provided file"
    with open(f"{temp_storage}/DataModelSchema", "r", encoding="utf-16le") as f:
        model_json = json.load(f)
    return model_json



def get_edges_from_expressions(nodes: list, expressions: list) -> list[tuple] :
    """
        FOR INTERNAL USE, YOU DO NOT NEED TO CALL THIS FUNCTION
        This function takes in input a list of nodes that need to be linked and the list "expressions" available in your DataModelSchema (model->expressions)
        In output, this function give a list of edges
    """
    edges = []

    # We are going to get the powerquery at {} model -> [] expressions -> X -> [] expression
    for expression in expressions :
        if expression["kind"] == 'm':
            query_names = []
            
            for query in expression["expression"]:
                query = query.strip()

                # We skip the "let" and "in" queries
                if query in ("let", "in"):
                    continue

                query_name = query.split("=")[0].strip()
                second_part = query[len(query_name)+1:].strip()


                # We find all the referenes to tables that begins with #" inn the powerquery
                matches = re.findall(r'#"[^"]*"', second_part)

                for match in matches :
                    match_without_quotes = match[2:-1]
                    if match_without_quotes in nodes : 
                        i = nodes.index(match_without_quotes)
                        edges.append((nodes[i], expression["name"]))

                # Removing all strings from the query
                second_part = re.sub(r'#"[^"]*"', '', second_part)
                second_part = re.sub(r'"[^"]*"', '', second_part)
                second_part = re.sub(r"'[^']*'", "", second_part)
                # BRUH
                second_part = re.sub(r"\[[^\]]*\]", "", second_part)

                # Removing all the references to previous queries :
                for query_name in query_names : 
                    second_part = re.sub(rf'(?<![a-zA-Z_0-9]){query_name}(?![a-zA-Z_0-9])', '', second_part)
                
                query_names.append(query_name)

                # Finding all the references to the rest of the queries
                for i, reference in enumerate(nodes):
                    matches = re.findall(rf'(?<![a-zA-Z_0-9]){reference}(?![a-zA-Z_0-9])', second_part)
                    if len(matches) > 0:
                        edges.append((nodes[i], expression["name"]))
    
    return edges



def get_edges_from_tables(nodes, tables):
    """
        FOR INTERNAL USE, YOU DO NOT NEED TO CALL THIS FUNCTION
        This function takes in input a list of nodes that need to be linked and the list "tables" available in your DataModelSchema (model->tables)
        In output, this function give a list of edges
    """
    edges = []

    # We are going to get the powerquery at {} model -> [] tables -> X -> {} source -> [] expression
    for table in tables :
        for partition in table["partitions"]:
            source = partition["source"]
            if source["type"] == 'm':
                whole_expression = "\n".join(source["expression"])
                lexer = PowerQueryLexer(InputStream(whole_expression))
                tokens = lexer.getAllTokens()
                token_set = set()
                for t in tokens:
                    if t.type == PowerQueryLexer.IDENTIFIER and t.text not in token_set:
                        if t.text in nodes:
                            edges.append((t.text, table["name"]))
                            token_set.add(t.text)
    return edges

def remove_forbiden_characters(graph):
    """
    Renames all nodes in a given NetworkX graph by replacing ':' with ''.

    Parameters:
    - graph: A NetworkX Graph object.
    """
    # Iterate over all nodes in the graph
    for node in graph.nodes():
        # Check if the node name contains ':'
        if ':' in node:
            # Replace ':' with ''
            new_node_name = node.replace(':', '')
            # Rename the node in the graph

            graph = nx.relabel_nodes( graph, {node: new_node_name})
    
    return graph

def get_model_digraph(filename:str, temp_storage:str):
    model_json = read_model_file(filename, temp_storage)
    nodes = get_model_nodes(model_json)
    
    for n in nodes:
        if n.startswith("DateTableTemplate"):
            nodes.remove(n)
            break

    edges = get_model_edges(model_json, nodes)

    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)
    return G


if __name__ == "__main__":
    filename = "example.pbit"
    temp_folder = "model"

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        if len(sys.argv) == 3:
            temp_folder = sys.argv[2]

    G = get_model_digraph(filename, temp_folder)
    G = remove_forbiden_characters(G)

    nx.drawing.nx_pydot.write_dot(G, "test.dot")

    nx.draw(G, with_labels=True)
    plt.show()