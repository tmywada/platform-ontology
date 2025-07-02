import os
import json
from extract_metadata_python import generate_metadata
from generate_graph import create_graph_from_metadata, create_html_visualization

def process_project_directory(directory_path: str) -> dict:
    # ... (this function remains the same as provided in the previous response) ...
    project_metadata = {}
    print(f"🔍 Starting to scan directory: {directory_path}")

    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                print(f"   - Processing: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        source_code = f.read()
                    
                    metadata = generate_metadata(source_code)
                    project_metadata[file_path] = metadata
                
                except (IOError, UnicodeDecodeError, SyntaxError) as e:
                    print(f"   - ❗️ Could not process file {file_path}: {e}")

    print("✅ Directory scan complete.")
    return project_metadata


if __name__ == "__main__":
    target_project_dir = './tests/data' 

    # 1. Generate metadata for the entire project
    metadata_collection = process_project_directory(target_project_dir)

    # 2. (Optional) Save metadata to a file
    output_filename = "project_metadata.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(metadata_collection, f, indent=2)
    print(f"✅ Project metadata saved to {output_filename}")

    # 3. Create a graph from the collected metadata
    print("\n--- Building Dependency Graph ---")
    code_graph = create_graph_from_metadata(metadata_collection, target_project_dir)
    
    print("\n--- Graph Creation Complete ---")
    print(f"📊 Graph contains {code_graph.number_of_nodes()} nodes and {code_graph.number_of_edges()} edges.")
    
    # 4. NEW: Visualize the graph and save it as an HTML file
    visualization_file = "code_dependency_graph.html"
    create_html_visualization(code_graph, visualization_file)
    
    # Example: Print all nodes and their types
    # print("\nNodes in graph:")
    # for node, data in code_graph.nodes(data=True):
    #     print(f"  - Node: {node} (Type: {data.get('node_type')})")