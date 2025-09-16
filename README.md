# Navigator

Campus navigation prototype using OpenStreetMap data, FastAPI backend, and Streamlit frontend.

## Project Structure
- `backend/` – FastAPI app for routing
- `viewer_app.py` – Streamlit viewer for map interaction
- `data/graphs/` – preprocessed OSM graph data (nodes, edges, metadata)

## Setup
1. Clone the repo and create a virtual environment:
   ```bash
   git clone https://github.com/saaranshpandey/navigator.git
   cd navigator
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   
2. Start the backend:
   ```uvicorn backend.app.main:app --reload```
   
4. Launch the streamlit viewer:
   ```streamlit run viewer_app.py```

## Usage
- Select a campus (e.g., UPenn) in the sidebar.
- Click on the map to set Source (green) and Target (red).
- Adjust preferences in the sidebar and compute a route.
- Results show distance, stairs, and indoor share, with the route drawn on the map.

## Next Steps
- Add markers for stairs and indoor transitions.
- Extend graph data to additional campuses.
- Package deployment (Docker or cloud).
- Explore support for alternate paths or waypoint routing.
