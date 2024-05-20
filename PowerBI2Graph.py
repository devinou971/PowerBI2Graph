import zipfile
import json
import re
import os
import networkx as nx
import matplotlib.pyplot as plt
import sys

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
    assert os.path.exists(f"{temp_storage}/DataModelSchema"), "There is no DataModelSchema in the provided file"
    with open(f"{temp_storage}/DataModelSchema", "r", encoding="utf-16le") as f:
        model_json = json.load(f)
    return model_json

def get_model_nodes(model: dict) -> list:
    """
        Gets the name of all the tables in the mode
    """
    tables = model["model"]["tables"]
    table_names = [table["partitions"][0]["name"] for table in tables]
    return table_names

def get_model_edges(model: dict, nodes: dict) -> list[tuple]:
    """
        Gets all the edges of the model.
        Returns a list of tuple representig the edges.
        For example : [(A, B), (B, C)]
    """
    tables = model["model"]["tables"]
    edges = []

    # We are going to get the powerquery at {} model -> [] tables -> X -> {} source -> [] expression
    for table in tables :
        for partition in table["partitions"]:
            source = partition["source"]
            if source["type"] == 'm':
                query_names = []
                for query in source["expression"]:
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
                            edges.append((nodes[i], partition["name"]))

                    # Removing all strings from the query
                    second_part = re.sub(r'#"[^"]*"', '', second_part)
                    second_part = re.sub(r'"[^"]*"', '', second_part)
                    second_part = re.sub(r"'[^']*'", "", second_part)

                    # Removing all the references to previous queries :
                    for query_name in query_names : 
                        second_part = re.sub(rf'(?<![a-zA-Z_0-9]){query_name}(?![a-zA-Z_0-9])', '', second_part)
                    
                    query_names.append(query_name)

                    # Finding all the references to the rest of the queries
                    for i, reference in enumerate(nodes):
                        matches = re.findall(rf'(?<![a-zA-Z_0-9]){reference}(?![a-zA-Z_0-9])', second_part)
                        if len(matches) > 0:
                            edges.append((nodes[i], partition["name"]))
    
    return edges

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
    
    print("Nodes:", G.nodes)
    print("Edges:", G.edges)

    # pos = {'N0': [3, 3], 'N1_1': [2 ,  2], 'N1_2': [ 4, 2], 'N2_1': [1, 1], 'N2_2': [3, 1], 'N2_3': [5,  1], 'N3_1': [2, 0], 'N3_2': [ 4, 0]}
    # nx.draw(G, pos=pos, with_labels=True)

    nx.draw(G, with_labels=True)
    plt.show()
