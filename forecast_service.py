import zipfile, os, tempfile, json, traceback
import pandas as pd
import plotly.graph_objects as go
from xgboost import XGBRegressor
from datetime import datetime
from calendar import month_abbr
from typing import Optional

# === Month mapping for filename → date conversion
month_map = {abbr: f"{i:02d}" for i, abbr in enumerate(month_abbr) if abbr}

def extract_date_from_filename(filename: str) -> Optional[str]:
    name = os.path.basename(filename)
    base, _ = os.path.splitext(name)
    match = pd.Series([base]).str.extract(r'([A-Za-z]{3})(\d{4})')
    if not match.isnull().values.any():
        mon, year = match.iloc[0]
        mm = month_map.get(mon.capitalize())
        if mm:
            return f"{year}-{mm}-01"
    return None

def create_features(df):
    df['month'] = df['ds'].dt.month
    df['year'] = df['ds'].dt.year
    return df

def forecast_kpi(df, country, tech, zone, kpi, forecast_months):
    try:
        filtered = df[
            (df['Country'] == country) &
            (df['Technology'] == tech) &
            (df['Zone'] == zone) &
            (df['KPI'] == kpi)
        ]
        if filtered.empty:
            return None, None, "No data available for the selected inputs"

        value_col = 'Actual Value MAPS Networks'
        if value_col not in filtered.columns:
            return None, None, f"Expected column '{value_col}' not found"

        ts = (
            filtered.groupby('Date')[value_col]
            .mean().reset_index()
            .rename(columns={'Date': 'ds', value_col: 'y'})
        )

        ts = ts.sort_values('ds')
        ts = create_features(ts)

        for lag in range(1, 4):
            ts[f'y_lag_{lag}'] = ts['y'].shift(lag)
        ts.dropna(inplace=True)

        X = ts[['month', 'year', 'y_lag_1', 'y_lag_2', 'y_lag_3']]
        y = ts['y']

        model = XGBRegressor(n_estimators=100)
        model.fit(X, y)

        last_row = ts.iloc[-1]
        future_dates = pd.date_range(start=ts['ds'].max() + pd.offsets.MonthBegin(),
                                     periods=forecast_months, freq='MS')

        forecasts = []
        prev_lags = [last_row['y_lag_1'], last_row['y_lag_2'], last_row['y_lag_3']]
        for date in future_dates:
            features = {
                'month': date.month,
                'year': date.year,
                'y_lag_1': prev_lags[0],
                'y_lag_2': prev_lags[1],
                'y_lag_3': prev_lags[2]
            }
            pred = model.predict(pd.DataFrame([features]))[0]
            forecasts.append({'ds': date, 'yhat': pred})
            prev_lags = [pred] + prev_lags[:2]

        forecast_df = pd.DataFrame(forecasts)

        fig = go.Figure([
            go.Scatter(x=ts['ds'], y=ts['y'], mode='lines+markers', name='Actual'),
            go.Scatter(x=forecast_df['ds'], y=forecast_df['yhat'], mode='lines+markers', name='Forecast')
        ])
        fig.update_layout(
            title=f"Forecast for {kpi} — {zone} | {tech} | {country}",
            xaxis_title="Date", yaxis_title=kpi
        )

        summary = "\n".join(
            f"{row['ds'].date()}: {row['yhat']:.2f}" for _, row in forecast_df.iterrows()
        )

        return fig, summary, None

    except Exception as e:
        return None, None, f"Forecast failed: {e}\n{traceback.format_exc()}"

def run_forecast_pipeline(zip_buffer, country, tech, zone, kpi, forecast_months=3):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_buffer)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmpdir)

            excel_files = []
            for root, _, files in os.walk(tmpdir):
                for fn in files:
                    if fn.lower().endswith((".xlsx", ".xls")):
                        excel_files.append(os.path.join(root, fn))

            if not excel_files:
                return None, None, "No Excel files found in ZIP archive"

            records = []
            for path in excel_files:
                try:
                    df = pd.read_excel(path)
                    df.columns = df.columns.str.strip()
                    date_str = extract_date_from_filename(path)
                    if date_str:
                        df['Date'] = pd.to_datetime(date_str)
                        df['source_file'] = os.path.basename(path)
                        records.append(df)
                except Exception:
                    continue

            if not records:
                return None, None, "No valid data found in Excel files"

            df_all = pd.concat(records, ignore_index=True)

            fig, summary, err = forecast_kpi(df_all, country, tech, zone, kpi, forecast_months)
            if err:
                return None, None, err

            plot_json_str = fig.to_json()
            plot_json = json.loads(plot_json_str)
            return plot_json, summary, None

    except Exception as e:
        return None, None, f"Pipeline error: {e}\n{traceback.format_exc()}"
