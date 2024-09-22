import streamlit as st
import pandas as pd
import requests
import io

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


def get_real_distance_osrm(origin, destination):
    # OSRM API endpoint
    url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{destination[1]},{destination[0]}?overview=false"

    response = requests.get(url)
    data = response.json()

    if response.status_code == 200 and 'routes' in data:
        distance_meters = data['routes'][0]['distance']
        return distance_meters
    else:
        st.error(f"Erro na requisição para a API OSRM: {data.get('message', 'Erro desconhecido')}")
        return None


# Função para maximizar a soma de UPS e buscar atividades que caibam no tempo restante
def maximize_ups_with_fitting_time(df_local, max_duration_hours):
    selected_activities = []
    previous_point = starting_point
    accumulated_time = 0

    # Ordenar pela maior UPS primeiro
    df_sorted_by_ups = df_local.sort_values(by='UPS', ascending=False)

    while not df_sorted_by_ups.empty and accumulated_time < max_duration_hours:
        # Verificar a atividade com maior UPS que caiba no tempo restante
        for index, row in df_sorted_by_ups.iterrows():
            distance = get_real_distance_osrm(previous_point, row['Coordenada Cartesiana'])
            if distance is None:
                continue  # Pula se houver erro na API

            time_to_travel = distance / vehicle_speed / 3600  # Tempo de deslocamento em horas
            execution_time = row['Tempo de Execução']
            total_time = time_to_travel + execution_time

            # Verificar se o tempo acumulado ainda está abaixo do limite de 10 horas
            if accumulated_time + total_time <= max_duration_hours:
                selected_activities.append(row)
                accumulated_time += total_time
                previous_point = row['Coordenada Cartesiana']
                # Remover a atividade já escolhida
                df_sorted_by_ups = df_sorted_by_ups.drop(index)
                break
        else:
            # Se nenhuma atividade restante couber no tempo, encerra a busca
            break

    # Criar DataFrame com as atividades selecionadas
    df_selected = pd.DataFrame(selected_activities)

    return df_selected, accumulated_time


# Função principal para execução no Streamlit
st.title("Otimização de Rotas para Maximizar UPS - OSRM API")

uploaded_file = st.file_uploader("Faça upload de um arquivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df_local = load_and_validate_excel(uploaded_file)
        st.success("Arquivo carregado e validado com sucesso!")
        st.write("Pré-visualização do arquivo:")
        st.dataframe(df_local.head())

        # Aplicar a nova abordagem para maximizar a soma de UPS respeitando o limite de tempo
        df_maximized_ups, total_time_maximized_ups = maximize_ups_with_fitting_time(df_local, max_duration_hours)

        # Exibir DataFrame otimizado
        st.write("Atividades Otimizadas para Maximizar UPS:")
        st.dataframe(df_maximized_ups)

        # Calcular a soma total de UPS no resultado maximizado
        total_ups_maximized = df_maximized_ups["UPS"].sum()

        st.write(f"**Soma total de UPS (Maximizada):** {total_ups_maximized:.2f}")
        st.write(f"**Tempo total acumulado (Horas):** {total_time_maximized_ups:.2f}")

        # Exportar para arquivo Excel (.xlsx)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_maximized_ups.to_excel(writer, index=False, sheet_name='Rota Otimizada')

        processed_data = output.getvalue()

        st.download_button(
            label="Baixar Rota Otimizada em Excel",
            data=processed_data,
            file_name="rota_otimizada_maximizada.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except ValueError as e:
        st.error(f"Erro: {str(e)}")
