from presidio_analyzer import AnalyzerEngine

def analyze_text_for_pii(text, language="en"):
    """
    Detect PII entities in text using Presidio.
    Returns a list of entity types.
    """
    analyzer = AnalyzerEngine()
    results = analyzer.analyze(text=text, language=language)
    return [res.entity_type for res in results]

def mark_pii_nodes(G):
    """
    Annotate graph nodes with 'pii' flags using Presidio.
    """
    for node, data in G.nodes(data=True):
        text_to_check = node + " " + str(data.get("value_repr", ""))
        entities = analyze_text_for_pii(text_to_check)
        if entities:
            G.nodes[node]["pii"] = True
            G.nodes[node]["pii_entities"] = entities
        else:
            G.nodes[node]["pii"] = False
            G.nodes[node]["pii_entities"] = []
