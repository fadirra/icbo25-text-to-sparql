from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from SPARQLWrapper import SPARQLWrapper, JSON
import requests
import pandas as pd
from dotenv import load_dotenv
import os
import json

def verbalize(qid):
    """
    Given a Wikidata QID (e.g., Q567), performs a SPARQL query to retrieve
    the set of direct (truthy) triples about that entity, excluding external IDs.

    Returns a formatted string containing a list of (subject, predicate, object) triples,
    where each triple is expressed using English labels and placed on a new line.
    """
    sparql_query = f"""
SELECT ?s ?sLabel ?p ?pLabel ?o ?oLabel WHERE {{
  BIND(wd:{qid} AS ?s)
  ?s ?pDirect ?o .
  ?p wikibase:directClaim ?pDirect .
  FILTER NOT EXISTS {{
    ?p wikibase:propertyType wikibase:ExternalId .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
}}
"""
    
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setQuery(sparql_query)
    sparql.addCustomHttpHeader("User-Agent", "MyWikidataApp/1.0 (mywikidata@example.com)")
    sparql.setReturnFormat(JSON)

    try:
        results = sparql.query().convert()
        triples = []
        for result in results["results"]["bindings"]:
            sLabel = result.get("sLabel", {}).get("value", "")
            pLabel = result.get("pLabel", {}).get("value", "")
            oLabel = result.get("oLabel", {}).get("value", "")
            triples.append(f"({sLabel}, {pLabel}, {oLabel})")
        result_string = "\n".join(triples)
    except Exception as e:
        result_string = f"SPARQL query failed: {e}"
    return result_string

def entity_link(entity_name):
    """
    Perform entity linking using Wikidata's wbsearchentities API.
    Given an entity name, return the most relevant Wikidata ID (e.g., Q252).
    """
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": entity_name
    }

    headers = {
        "User-Agent": "MyResearchApp/1.0 (+https://github.com/yourname/yourrepo; contact@yourdomain.com)"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        results = response.json().get("search", [])
        if results:
            return results[0].get("id")  # Return top result's ID
        else:
            return None
    except requests.RequestException as e:
        print(f"API error: {e}")
        return None

def extract_entity_property(question, llm):
    """
    Extracts the main entity and property from a natural language question.
    Returns a dictionary: { "entity": ..., "property": ... }
    """

    prompt = PromptTemplate.from_template("""
    You are an expert information extraction assistant.

    Given a natural language question, extract:
    1. The most specific main entity being discussed. This must be a proper noun, and if the question refers to a specific event, incident, or action involving an entity, prioritize that specific event (including the entity involved) as the main entity.
    2. The main property or attribute being asked about, must be a common noun (e.g., "children", "population", "net worth")

    Respond using **only JSON format** like this:
    {{
      "entity": "...",
      "property": "..."
    }}

    If the question is ambiguous or not about a specific entity and property, respond with:
    {{
      "entity": null,
      "property": null
    }}

    Question:
    {question}
    """)

    chain = prompt | llm

    try:
        response = chain.invoke({"question": question})
        return json.loads(response)

    except Exception as e:
        return {"entity": None, "property": None, "error": str(e)}
