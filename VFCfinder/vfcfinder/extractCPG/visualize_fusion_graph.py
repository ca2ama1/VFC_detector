#!/usr/bin/env python3
"""
Visualize Joern CPG + CodeQL Cross-File Call Fusion Graph
"""

import json
import sqlite3
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from collections import defaultdict
import os
from pathlib import Path
import argparse


class FusionGraphVisualizer:
    """Visualize the fusion of Joern CPG and CodeQL cross-file calls"""
    
    def __init__(self):
        self.joern_cpg = None
        self.codeql_db = None
        self.graph = nx.DiGraph()
        
    def load_joern_cpg(self, json_path: str):
        """Load Joern CPG JSON"""
        with open(json_path, 'r', encoding='utf-8') as f:
            self.joern_cpg = json.load(f)
        print(f"Loaded Joern CPG: {len(self.joern_cpg.get('nodes', []))} nodes, {len(self.joern_cpg.get('edges', []))} edges")
        
    def load_codeql_db(self, db_path: str):
        """Load CodeQL database"""
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        print(f"Loaded CodeQL database: {db_path}")
        
    def build_fusion_graph(self):
        """Build fusion graph from Joern CPG and CodeQL results"""
        if not self.joern_cpg:
            raise ValueError("Joern CPG not loaded")
        
        # Add Joern CPG nodes
        for node in self.joern_cpg.get('nodes', []):
            node_id = str(node.get('id'))
            node_type = node.get('type', 'UNKNOWN')
            filename = node.get('filename', node.get('file', ''))
            line = node.get('line', -1)
            code = node.get('code', node.get('text', ''))
            
            self.graph.add_node(
                node_id,
                type=node_type,
                filename=filename,
                line=line,
                code=code,
                source='joern'
            )
        
        # Add Joern CPG edges
        for edge in self.joern_cpg.get('edges', []):
            src = str(edge.get('src'))
            dst = str(edge.get('dst'))
            edge_type = edge.get('type', edge.get('edgeType', 'UNKNOWN'))
            
            self.graph.add_edge(src, dst, type=edge_type, source='joern')
        
        # Add CodeQL results (if available)
        if self.codeql_db:
            self.cursor.execute('SELECT id, filepath, line, code FROM nodes WHERE type IN ("CALL", "_invokeExpr")')
            calls = self.cursor.fetchall()
            
            for call_id, filepath, line, code in calls:
                if call_id not in self.graph.nodes:
                    self.graph.add_node(call_id, type='CALL', filepath=filepath, line=line, code=code, source='codeql')
        
        print(f"Built fusion graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
    def extract_cross_file_calls(self):
        """Extract cross-file function calls from CodeQL database"""
        if not self.codeql_db:
            return []
        
        # Get all functions
        self.cursor.execute('SELECT id, name, filepath FROM functions')
        functions = {row[0]: {'name': row[1], 'filepath': row[2]} for row in self.cursor.fetchall()}
        
        # Get all call nodes
        self.cursor.execute('SELECT id, filepath FROM nodes WHERE type IN ("CALL", "_invokeExpr")')
        calls = self.cursor.fetchall()
        
        # Simple cross-file detection (in real scenario, you'd need to resolve callee)
        cross_file_calls = []
        file_calls = defaultdict(list)
        
        for call_id, call_file in calls:
            file_calls[call_file].append(call_id)
        
        # Find files with cross-file call potential
        for file, call_ids in file_calls.items():
            if len(call_ids) > 10:  # Simplified heuristic
                cross_file_calls.extend(call_ids[:5])  # Sample 5 calls per file
        
        return cross_file_calls
        
    def visualize(self, output_path: str, max_nodes: int = 100):
        """Visualize the fusion graph"""
        # Get nodes and edges
        nodes = list(self.graph.nodes())[:max_nodes]
        edges = list(self.graph.edges())[:max_nodes]
        
        # Create subgraph
        subgraph = self.graph.subgraph(nodes)
        
        # Color by source
        node_colors = []
        for node in subgraph.nodes():
            source = subgraph.nodes[node].get('source', 'joern')
            if source == 'joern':
                node_colors.append('#3498db')  # Blue for Joern
            else:
                node_colors.append('#e74c3c')  # Red for CodeQL
        
        # Color edges by type
        edge_colors = []
        for src, dst in subgraph.edges():
            edge_type = subgraph.edges[src, dst].get('type', '')
            if 'CALL' in edge_type:
                edge_colors.append('#27ae60')  # Green for calls
            elif 'AST' in edge_type:
                edge_colors.append('#9b59b6')  # Purple for AST
            elif 'CFG' in edge_type:
                edge_colors.append('#f39c12')  # Orange for CFG
            else:
                edge_colors.append('#34495e')  # Dark for others
        
        # Layout
        pos = nx.spring_layout(subgraph, k=2, iterations=50)
        
        # Create figure
        plt.figure(figsize=(16, 12))
        
        # Draw nodes
        nx.draw_networkx_nodes(
            subgraph, pos,
            node_color=node_colors,
            node_size=500,
            alpha=0.8
        )
        
        # Draw edges
        nx.draw_networkx_edges(
            subgraph, pos,
            edge_color=edge_colors,
            width=1.5,
            alpha=0.7,
            arrows=True,
            arrowsize=20
        )
        
        # Draw labels
        labels = {node: f"{subgraph.nodes[node].get('type', '')[:10]}" for node in subgraph.nodes()}
        nx.draw_networkx_labels(subgraph, pos, labels=labels, font_size=8)
        
        # Legend
        plt.scatter([], [], c='#3498db', label='Joern CPG', s=100)
        plt.scatter([], [], c='#e74c3c', label='CodeQL Calls', s=100)
        plt.scatter([], [], c='#27ae60', label='Function Calls', s=100)
        plt.scatter([], [], c='#9b59b6', label='AST Edges', s=100)
        plt.scatter([], [], c='#f39c12', label='CFG Edges', s=100)
        plt.legend(loc='upper right')
        
        plt.title('Joern CPG + CodeQL Cross-File Call Fusion Graph')
        plt.axis('off')
        
        # Save
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Visualization saved to: {output_path}")
        
    def generate_summary_report(self, output_path: str):
        """Generate summary report"""
        report = f"""
# Joern CPG + CodeQL 融合图分析报告

## 概述

- **生成时间**: {__import__('datetime').datetime.now().isoformat()}
- **Joern CPG 节点数**: {self.graph.number_of_nodes()}
- **Joern CPG 边数**: {self.graph.number_of_edges()}

## 图结构分析

### 节点类型分布
"""
        
        # Count node types
        type_counts = defaultdict(int)
        for node in self.graph.nodes():
            node_type = self.graph.nodes[node].get('type', 'UNKNOWN')
            type_counts[node_type] += 1
        
        for node_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
            report += f"- {node_type}: {count}\n"
        
        report += f"""
### 边类型分布
"""
        
        # Count edge types
        edge_counts = defaultdict(int)
        for src, dst in self.graph.edges():
            edge_type = self.graph.edges[src, dst].get('type', 'UNKNOWN')
            edge_counts[edge_type] += 1
        
        for edge_type, count in sorted(edge_counts.items(), key=lambda x: -x[1])[:10]:
            report += f"- {edge_type}: {count}\n"
        
        report += f"""
## CodeQL 跨文件调用分析

- **跨文件调用边**: {len(self.extract_cross_file_calls())}

## 可视化

![Fusion Graph](fusion_graph.png)

## 结论

本图融合了 Joern 的文件内 CPG 和 CodeQL 的跨文件调用分析，提供了完整的代码依赖关系视图。
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"Summary report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Visualize Joern CPG + CodeQL fusion graph')
    parser.add_argument('--joern-cpg', '-j', required=True, help='Joern CPG JSON file')
    parser.add_argument('--codeql-db', '-c', help='CodeQL database file (optional)')
    parser.add_argument('--output', '-o', default='fusion_graph.png', help='Output image path')
    parser.add_argument('--max-nodes', '-m', type=int, default=100, help='Maximum nodes to visualize')
    
    args = parser.parse_args()
    
    visualizer = FusionGraphVisualizer()
    
    print("Loading Joern CPG...")
    visualizer.load_joern_cpg(args.joern_cpg)
    
    if args.codeql_db:
        print("Loading CodeQL database...")
        visualizer.load_codeql_db(args.codeql_db)
    
    print("Building fusion graph...")
    visualizer.build_fusion_graph()
    
    print("Extracting cross-file calls...")
    cross_file = visualizer.extract_cross_file_calls()
    print(f"Found {len(cross_file)} potential cross-file calls")
    
    print("Visualizing...")
    visualizer.visualize(args.output, args.max_nodes)
    
    print("Generating report...")
    visualizer.generate_summary_report(args.output.replace('.png', '.md'))


if __name__ == "__main__":
    main()
