from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
from datetime import datetime
import json

# Connection parameters
url = 'http://<influxDB-service-external-address>:8086'
token = 'secret-token'
org = 'InfluxData'  # you may replace with your org name
bucket = 'manufacturing' # you may replace with your bucket name

# Creating the InfluxDB client
client = InfluxDBClient(url=url, token=token, org=org)
# Write API for writing data
write_api = client.write_api(write_options=SYNCHRONOUS)

# Sample data in JSON format
# Read CSV file into pandas DataFrame
df = pd.read_csv('<path-of-your-csv-data-file>.csv')
tmp=df.head()
# Convert DataFrame to JSON format
json_data = tmp.to_json(orient='records')
data_list = json.loads(json_data)

# Writing data to InfluxDB
for row_data in data_list:
    point = (
        Point("measurement_name")
        .tag("tag_key", "tag_value")
        .field("product", row_data['Product']) # replace with your field parrmeter name
        .field("diametro", row_data['Diametro Promedio Actual (mils) - Medidor de diametro']) # replace with your field parrmeter name
        .time(datetime.strptime(row_data['Factory Time'], '%d/%m/%Y %H:%M').isoformat() + 'Z', WritePrecision.NS)
    )
    write_api.write(bucket=bucket, org=org, record=point)

print("Write data points done")

# Close the client
client.close()
 