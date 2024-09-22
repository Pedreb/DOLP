import streamlit as st
import pandas as pd
import googlemaps
from datetime import datetime
import streamlit.components.v1 as components

# Inicializar o cliente Google Maps com a sua chave de API
gmaps = googlemaps.Client(key='AIzaSyC9tYj476jcrBY0WDNY0z33zuzllXbqKYY')

# Ponto de partida fornecido
starting_point = (-15.630592, -55.954662)

# Velocidade do veículo em metros por segundo (25 km/h = 6.94444 metros por segundo)
vehicle_speed = 25 * 1000 / 3600  # Convertendo km/h para m/s

# Tempo máximo em horas (10 horas)
max_duration_hours = 10


def load_and_validate_excel(file):
    df_local = pd.read_excel(file)

    required_columns = ['Atividade', 'UPS', 'Coordenada Cartesiana', 'Tempo de Execução']
    if list(df_local.columns) != required_columns:
        raise ValueError(f"O arquivo deve conter as colunas: {required_columns}")

    if not pd.api.types.is_string_dtype(df_local['Atividade']):
        raise ValueError("A coluna 'Atividade' deve conter apenas texto.")
    if not pd.api.types.is_numeric_dtype(df_local['UPS']):
        raise ValueError("A coluna 'UPS' deve conter apenas números.")
    if not pd.api.types.is_numeric_dtype(df_local['Tempo de Execução']):
        raise ValueError("A coluna 'Tempo de Execução' deve conter apenas números.")

    try:
        df_local['Coordenada Cartesiana'] = df_local['Coordenada Cartesiana'].apply(
            lambda x: eval(x) if isinstance(x, str) else x)
        for coord in df_local['Coordenada Cartesiana']:
            if not (isinstance(coord, tuple) and len(coord) == 2):
                raise ValueError
    except:
        raise ValueError("A coluna 'Coordenada Cartesiana' deve conter coordenadas no formato (latitude, longitude).")

    return df_local


def get_real_distance(origin, destination):
    now = datetime.now()
    result = gmaps.distance_matrix(origins=[origin], destinations=[destination], mode="driving", departure_time=now)
    distance_meters = result['rows'][0]['elements'][0]['distance']['value']
    return distance_meters


def optimize_route(df_local):
    ups_per_distance_time = []
    distances = []
    times = []
    activity_times = []
    execution_times = []
    selected_activities = []
    previous_point = starting_point
    accumulated_time = 0

    for index, row in df_local.iterrows():
        distance = get_real_distance(previous_point, row['Coordenada Cartesiana'])
        time_to_travel = distance / vehicle_speed / 3600  # Tempo de deslocamento em horas
        activity_time = row['UPS']
        execution_time = row['Tempo de Execução']

        total_time = time_to_travel + execution_time

        if accumulated_time + total_time <= max_duration_hours:
            ups_ratio = row['UPS'] / (distance + execution_time)  # UPS / (distância + tempo de execução)
            ups_per_distance_time.append(ups_ratio)
            distances.append(distance)
            times.append(time_to_travel)
            activity_times.append(activity_time)
            execution_times.append(execution_time)
            selected_activities.append(row)
            previous_point = row['Coordenada Cartesiana']
            accumulated_time += total_time
        else:
            break

    df_selected = pd.DataFrame(selected_activities)
    df_selected["UPS/(Distância + Tempo de Execução)"] = ups_per_distance_time
    df_selected["Distância entre Trechos (m)"] = distances
    df_selected["Tempo de Deslocamento (h)"] = times
    df_selected["UPS da Atividade"] = activity_times
    df_selected["Tempo de Execução (h)"] = execution_times
    df_selected["Distância (km)"] = df_selected["Distância entre Trechos (m)"] / 1000

    return df_selected


# Função para gerar HTML com rotas otimizadas
def display_google_maps_with_routes(df_selected):
    # Gerar waypoints das coordenadas otimizadas para a Directions API
    waypoints = []
    for index, row in df_selected.iterrows():
        lat, lon = row['Coordenada Cartesiana']
        waypoints.append(f"{lat},{lon}")

    # Montar URL com a API Directions
    origin = waypoints[0]
    destination = waypoints[-1]
    waypoint_str = '|'.join(waypoints[1:-1])  # Todos os pontos intermediários

    google_maps_html = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>Rotas Otimizadas</title>
        <script async src="https://maps.googleapis.com/maps/api/js?key=AIzaSyC9tYj476jcrBY0WDNY0z33zuzllXbqKYY&callback=console.debug&libraries=maps,marker,directions">
        </script>
        <style>
          #map {{
            height: 100%;
          }}

          html,
          body {{
            height: 100%;
            margin: 0;
            padding: 0;
          }}
        </style>
      </head>
      <body>
        <div id="map"></div>
        <script>
            function initMap() {{
              const directionsService = new google.maps.DirectionsService();
              const directionsRenderer = new google.maps.DirectionsRenderer();
              const map = new google.maps.Map(document.getElementById("map"), {{
                zoom: 14,
                center: {{lat: {waypoints[0].split(',')[0]}, lng: {waypoints[0].split(',')[1]}}},
              }});
              directionsRenderer.setMap(map);

              const request = {{
                origin: '{origin}',
                destination: '{destination}',
                waypoints: [{','.join([f'{{location: "{wp}"}}' for wp in waypoints[1:-1]])}],
                travelMode: google.maps.TravelMode.DRIVING,
              }};
              directionsService.route(request, (result, status) => {{
                if (status == 'OK') {{
                  directionsRenderer.setDirections(result);
                }} else {{
                  window.alert('Directions request failed due to ' + status);
                }}
              }});
            }}
            google.maps.event.addDomListener(window, 'load', initMap);
        </script>
      </body>
    </html>
    """
    components.html(google_maps_html, height=600)


# Função principal para execução no Streamlit
st.title("Otimização de Rotas para Atividades Elétricas")

uploaded_file = st.file_uploader("Faça upload de um arquivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df_local = load_and_validate_excel(uploaded_file)
        st.success("Arquivo carregado e validado com sucesso!")
        st.write("Pré-visualização do arquivo:")
        st.dataframe(df_local.head())

        # Otimizar rota
        df_optimized = optimize_route(df_local)
        st.write("Rota Otimizada:")
        st.dataframe(df_optimized)

        # Exibir Google Maps com rotas otimizadas
        st.write("Google Maps com Rotas Otimizadas:")
        display_google_maps_with_routes(df_optimized)

    except ValueError as e:
        st.error(f"Erro: {str(e)}")
