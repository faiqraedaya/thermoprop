"""
File I/O utilities for ThermoProp application
"""

import json
import pandas as pd
from typing import Dict, Any, List

class FileIO:
    """Utility class for file input/output operations"""

    @staticmethod
    def export_results(filename: str, results: Dict[str, Any]) -> bool:
        """
        Export calculation results to file

        Args:
            filename: Output file path
            results: Dictionary of results to export

        Returns:
            True if successful, False otherwise
        """
        try:
            if filename.endswith('.xlsx'):
                return FileIO._export_to_excel(filename, results)
            elif filename.endswith('.csv'):
                return FileIO._export_to_csv(filename, results)
            else:
                return FileIO._export_to_json(filename, results)
        except Exception as e:
            print(f"Export error: {str(e)}")
            return False

    @staticmethod
    def _export_to_excel(filename: str, results: Dict[str, Any]) -> bool:
        """Export results to Excel file"""
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                for sheet_name, data in results.items():
                    if isinstance(data, pd.DataFrame):
                        data.to_excel(writer, sheet_name=sheet_name, index=False)
                    elif isinstance(data, list) and len(data) > 0:
                        df = pd.DataFrame(data)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    elif isinstance(data, dict):
                        # Convert dict to DataFrame
                        df_data = []
                        for key, value in data.items():
                            if isinstance(value, tuple) and len(value) == 2:
                                df_data.append([key, value[0], value[1]])
                            else:
                                df_data.append([key, str(value), ''])
                        df = pd.DataFrame(df_data, columns=['Property', 'Value', 'Unit'])
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            return True
        except Exception as e:
            print(f"Excel export error: {str(e)}")
            return False

    @staticmethod
    def _export_to_csv(filename: str, results: Dict[str, Any]) -> bool:
        """Export results to CSV file"""
        try:
            # For CSV, we'll export the first result set
            if results:
                first_key = list(results.keys())[0]
                data = results[first_key]

                if isinstance(data, pd.DataFrame):
                    data.to_csv(filename, index=False)
                elif isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    df.to_csv(filename, index=False)
                elif isinstance(data, dict):
                    # Convert dict to DataFrame
                    df_data = []
                    for key, value in data.items():
                        if isinstance(value, tuple) and len(value) == 2:
                            df_data.append([key, value[0], value[1]])
                        else:
                            df_data.append([key, str(value), ''])
                    df = pd.DataFrame(df_data, columns=['Property', 'Value', 'Unit'])
                    df.to_csv(filename, index=False)
            return True
        except Exception as e:
            print(f"CSV export error: {str(e)}")
            return False

    @staticmethod
    def _export_to_json(filename: str, results: Dict[str, Any]) -> bool:
        """Export results to JSON file"""
        try:
            # Convert results to JSON-serializable format
            json_data = {}
            for key, value in results.items():
                if isinstance(value, pd.DataFrame):
                    json_data[key] = value.to_dict('records')
                elif isinstance(value, dict):
                    json_data[key] = value
                else:
                    json_data[key] = str(value)

            with open(filename, 'w') as f:
                json.dump(json_data, f, indent=2)
            return True
        except Exception as e:
            print(f"JSON export error: {str(e)}")
            return False

    @staticmethod
    def table_to_dataframe(table) -> pd.DataFrame:
        """
        Convert QTableWidget to pandas DataFrame

        Args:
            table: QTableWidget instance

        Returns:
            pandas DataFrame
        """
        try:
            data = []
            headers = []

            # Get headers
            for col in range(table.columnCount()):
                header_item = table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"Column_{col}")

            # Get data
            for row in range(table.rowCount()):
                row_data = []
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)

            return pd.DataFrame(data, columns=headers)
        except Exception as e:
            print(f"Table conversion error: {str(e)}")
            return pd.DataFrame()
