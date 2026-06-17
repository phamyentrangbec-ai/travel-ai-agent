"""
static_data.py — City data loader with rich knowledge base priority.

Load order:
  1. data/knowledge_bases/{slug}.json  (rich format — preferred)
  2. data/genz_spots.json              (legacy simple format — fallback)
  3. None         