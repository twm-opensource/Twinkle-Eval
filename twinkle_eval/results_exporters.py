import csv
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

import pandas as pd


class ResultsExporter(ABC):
    """Abstract base class for results exporters."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def export(self, results: Dict[str, Any], output_path: str) -> str:
        """Export results to specified format."""
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get the file extension for this exporter."""
        pass


class JSONExporter(ResultsExporter):
    """Export results to JSON format."""

    def get_file_extension(self) -> str:
        return ".json"

    def export(self, results: Dict[str, Any], output_path: str) -> str:
        """Export results to JSON file."""
        if not output_path.endswith(self.get_file_extension()):
            output_path += self.get_file_extension()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

        return output_path


class CSVExporter(ResultsExporter):
    """Export results to CSV format."""

    def get_file_extension(self) -> str:
        return ".csv"

    def export(self, results: Dict[str, Any], output_path: str) -> str:
        """Export results to CSV file."""
        if not output_path.endswith(self.get_file_extension()):
            output_path += self.get_file_extension()

        # Flatten the results structure for CSV export
        flattened_data = self._flatten_results(results)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            if flattened_data:
                writer = csv.DictWriter(f, fieldnames=flattened_data[0].keys())
                writer.writeheader()
                writer.writerows(flattened_data)

        return output_path

    def _flatten_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten nested results structure for CSV export."""
        flattened = []

        timestamp = results.get("timestamp", "")
        config = results.get("config", {})
        environment = config.get("environment", {})
        
        base_info = {
            "timestamp": timestamp,
            "config_model_name": config.get("model", {}).get("name", ""),
            "config_temperature": config.get("model", {}).get("temperature", ""),
            "gpu_model": environment.get("gpu_info", {}).get("model", ""),
            "gpu_count": environment.get("gpu_info", {}).get("count", ""),
            "gpu_memory_gb": environment.get("gpu_info", {}).get("memory_gb", ""),
            "cuda_version": environment.get("gpu_info", {}).get("cuda_version", ""),
            "tp_size": environment.get("parallel_config", {}).get("tp_size", ""),
            "pp_size": environment.get("parallel_config", {}).get("pp_size", ""),
            "framework": environment.get("system_info", {}).get("framework", ""),
        }

        for dataset_path, dataset_data in results.get("dataset_results", {}).items():
            dataset_info = base_info.copy()
            dataset_info.update(
                {
                    "dataset_path": dataset_path,
                    "dataset_average_accuracy": dataset_data.get("average_accuracy", 0),
                    "dataset_average_std": dataset_data.get("average_std", 0),
                }
            )

            for file_result in dataset_data.get("results", []):
                file_info = dataset_info.copy()
                file_info.update(
                    {
                        "file": file_result.get("file", ""),
                        "accuracy_mean": file_result.get("accuracy_mean", 0),
                        "accuracy_std": file_result.get("accuracy_std", 0),
                    }
                )
                flattened.append(file_info)

        return flattened


class ExcelExporter(ResultsExporter):
    """Export results to Excel format."""

    def get_file_extension(self) -> str:
        return ".xlsx"

    def export(self, results: Dict[str, Any], output_path: str) -> str:
        """Export results to Excel file."""
        if not output_path.endswith(self.get_file_extension()):
            output_path += self.get_file_extension()

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Summary sheet
            summary_data = self._create_summary_data(results)
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Detailed results for each dataset
            for dataset_path, dataset_data in results.get("dataset_results", {}).items():
                sheet_name = os.path.basename(dataset_path)[:30]  # Excel sheet name limit
                detailed_data = self._create_detailed_data(dataset_data)
                if detailed_data:
                    detailed_df = pd.DataFrame(detailed_data)
                    detailed_df.to_excel(writer, sheet_name=sheet_name, index=False)

        return output_path

    def _create_summary_data(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create summary data for Excel export."""
        summary = []
        
        config = results.get("config", {})
        environment = config.get("environment", {})

        for dataset_path, dataset_data in results.get("dataset_results", {}).items():
            summary.append(
                {
                    "Dataset": dataset_path,
                    "Average Accuracy": dataset_data.get("average_accuracy", 0),
                    "Standard Deviation": dataset_data.get("average_std", 0),
                    "Number of Files": len(dataset_data.get("results", [])),
                    "GPU Model": environment.get("gpu_info", {}).get("model", ""),
                    "GPU Count": environment.get("gpu_info", {}).get("count", ""),
                    "TP Size": environment.get("parallel_config", {}).get("tp_size", ""),
                    "PP Size": environment.get("parallel_config", {}).get("pp_size", ""),
                    "Framework": environment.get("system_info", {}).get("framework", ""),
                }
            )

        return summary

    def _create_detailed_data(self, dataset_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create detailed data for Excel export."""
        detailed = []

        for file_result in dataset_data.get("results", []):
            detailed.append(
                {
                    "File": file_result.get("file", ""),
                    "Accuracy Mean": file_result.get("accuracy_mean", 0),
                    "Accuracy Std": file_result.get("accuracy_std", 0),
                    "Individual Accuracies": str(
                        file_result.get("individual_runs", {}).get("accuracies", [])
                    ),
                }
            )

        return detailed


class HTMLExporter(ResultsExporter):
    """Export results to HTML format."""

    def get_file_extension(self) -> str:
        return ".html"

    def export(self, results: Dict[str, Any], output_path: str) -> str:
        """Export results to HTML file."""
        if not output_path.endswith(self.get_file_extension()):
            output_path += self.get_file_extension()

        html_content = self._generate_html(results)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def _generate_html(self, results: Dict[str, Any]) -> str:
        """Generate HTML content from results."""
        timestamp = results.get("timestamp", "")
        config = results.get("config", {})
        environment = config.get("environment", {})
        gpu_info = environment.get("gpu_info", {})
        parallel_config = environment.get("parallel_config", {})
        system_info = environment.get("system_info", {})

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Twinkle Eval Results - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .environment {{ background-color: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .env-section {{ margin: 10px 0; }}
        .dataset {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; }}
        .dataset-header {{ background-color: #e8f4f8; padding: 15px; }}
        .results-table {{ width: 100%; border-collapse: collapse; }}
        .results-table th, .results-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .results-table th {{ background-color: #f2f2f2; }}
        .accuracy {{ color: #2e7d32; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌟 Twinkle Eval Results</h1>
        <p><strong>Timestamp:</strong> {timestamp}</p>
        <p><strong>Model:</strong> {config.get("model", {}).get("name", "N/A")}</p>
        <p><strong>Temperature:</strong> {config.get("model", {}).get("temperature", "N/A")}</p>
    </div>
    
    <div class="environment">
        <h2>🖥️ Environment Information</h2>
        <div class="env-section">
            <h3>GPU Configuration</h3>
            <p><strong>Model:</strong> {gpu_info.get("model", "N/A")}</p>
            <p><strong>Count:</strong> {gpu_info.get("count", "N/A")}</p>
            <p><strong>Memory:</strong> {gpu_info.get("memory_gb", "N/A")} GB</p>
            <p><strong>CUDA Version:</strong> {gpu_info.get("cuda_version", "N/A")}</p>
        </div>
        <div class="env-section">
            <h3>Parallel Configuration</h3>
            <p><strong>TP Size:</strong> {parallel_config.get("tp_size", "N/A")}</p>
            <p><strong>PP Size:</strong> {parallel_config.get("pp_size", "N/A")}</p>
        </div>
        <div class="env-section">
            <h3>System Information</h3>
            <p><strong>Framework:</strong> {system_info.get("framework", "N/A")}</p>
            <p><strong>Python Version:</strong> {system_info.get("python_version", "N/A")}</p>
            <p><strong>PyTorch Version:</strong> {system_info.get("torch_version", "N/A")}</p>
            <p><strong>Node Count:</strong> {system_info.get("node_count", "N/A")}</p>
        </div>
    </div>
"""

        for dataset_path, dataset_data in results.get("dataset_results", {}).items():
            html += f"""
    <div class="dataset">
        <div class="dataset-header">
            <h2>📊 Dataset: {dataset_path}</h2>
            <p><strong>Average Accuracy:</strong> <span class="accuracy">{dataset_data.get("average_accuracy", 0):.2%}</span></p>
            <p><strong>Standard Deviation:</strong> {dataset_data.get("average_std", 0):.4f}</p>
        </div>
        <table class="results-table">
            <tr>
                <th>File</th>
                <th>Accuracy Mean</th>
                <th>Accuracy Std</th>
            </tr>
"""

            for file_result in dataset_data.get("results", []):
                html += f"""
            <tr>
                <td>{file_result.get("file", "")}</td>
                <td class="accuracy">{file_result.get("accuracy_mean", 0):.2%}</td>
                <td>{file_result.get("accuracy_std", 0):.4f}</td>
            </tr>
"""

            html += """
        </table>
    </div>
"""

        html += """
</body>
</html>
"""

        return html


class ResultsExporterFactory:
    """Factory class for creating results exporters."""

    _registry: Dict[str, Type[ResultsExporter]] = {
        "json": JSONExporter,
        "csv": CSVExporter,
        "excel": ExcelExporter,
        "html": HTMLExporter,
    }

    @classmethod
    def register_exporter(cls, name: str, exporter_class: Type[ResultsExporter]):
        """Register a new results exporter."""
        if not issubclass(exporter_class, ResultsExporter):
            raise ValueError(f"Exporter class must inherit from ResultsExporter base class")
        cls._registry[name] = exporter_class

    @classmethod
    def create_exporter(
        cls, exporter_type: str, config: Optional[Dict[str, Any]] = None
    ) -> ResultsExporter:
        """Create a results exporter instance based on type."""
        if exporter_type not in cls._registry:
            available_types = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unsupported exporter type: {exporter_type}. Available types: {available_types}"
            )

        exporter_class = cls._registry[exporter_type]
        return exporter_class(config)

    @classmethod
    def get_available_types(cls) -> List[str]:
        """Get list of available exporter types."""
        return list(cls._registry.keys())

    @classmethod
    def export_results(
        cls, results: Dict[str, Any], output_path: str, formats: List[str]
    ) -> List[str]:
        """Export results to multiple formats."""
        exported_files = []

        for format_type in formats:
            try:
                exporter = cls.create_exporter(format_type)
                base_path = os.path.splitext(output_path)[0]
                format_path = base_path + exporter.get_file_extension()
                exported_file = exporter.export(results, format_path)
                exported_files.append(exported_file)
            except Exception as e:
                print(f"⚠️ Warning: Failed to export to {format_type}: {e}")

        return exported_files
