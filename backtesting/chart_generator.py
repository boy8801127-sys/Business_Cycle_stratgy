"""
績效報告和圖表生成模組
生成所有策略的績效比較圖表，以及每個策略的詳細分析圖表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class ChartGenerator:
    """圖表生成器"""
    
    def __init__(self, results, price_data, cycle_data, m1b_data=None):
        """
        初始化圖表生成器
        
        參數:
        - results: 回測結果字典 {strategy_name: result_dict}
        - price_data: 股價資料 DataFrame（包含 date, ticker, close）
        - cycle_data: 景氣燈號資料 DataFrame（包含 date, score）
        - m1b_data: M1B 資料 DataFrame（可選）
        """
        self.results = results
        self.price_data = price_data.copy()
        self.cycle_data = cycle_data.copy()
        self.m1b_data = m1b_data.copy() if m1b_data is not None else None
        
        # 處理日期格式
        if 'date' in self.price_data.columns:
            if isinstance(self.price_data['date'].iloc[0], str):
                self.price_data['date'] = pd.to_datetime(self.price_data['date'], format='%Y%m%d')
            self.price_data['date'] = pd.to_datetime(self.price_data['date']).dt.date
        
        if 'date' in self.cycle_data.columns:
            if isinstance(self.cycle_data['date'].iloc[0], str):
                self.cycle_data['date'] = pd.to_datetime(self.cycle_data['date'], format='%Y%m%d')
            self.cycle_data['date'] = pd.to_datetime(self.cycle_data['date']).dt.date
        
        if self.m1b_data is not None and 'date' in self.m1b_data.columns:
            if isinstance(self.m1b_data['date'].iloc[0], str):
                self.m1b_data['date'] = pd.to_datetime(self.m1b_data['date'], format='%Y%m%d')
            self.m1b_data['date'] = pd.to_datetime(self.m1b_data['date']).dt.date
    
    def generate_all_strategies_comparison(self, output_dir, format='both'):
        """
        生成所有策略績效比較圖表
        
        參數:
        - output_dir: 輸出目錄
        - format: 輸出格式 ('png', 'html', 'both')
        """
        if format in ['png', 'both']:
            self._generate_comparison_png(output_dir)
        if format in ['html', 'both']:
            self._generate_comparison_html(output_dir)
    
    def generate_strategy_detail(self, strategy_name, strategy_result, output_dir, format='both'):
        """
        生成單一策略詳細分析圖表
        
        參數:
        - strategy_name: 策略名稱
        - strategy_result: 策略回測結果字典
        - output_dir: 輸出目錄
        - format: 輸出格式 ('png', 'html', 'both')
        """
        if format in ['png', 'both']:
            self._generate_detail_png(strategy_name, strategy_result, output_dir)
        if format in ['html', 'both']:
            self._generate_detail_html(strategy_name, strategy_result, output_dir)
    
    def _generate_comparison_png(self, output_dir):
        """生成所有策略績效比較圖表（PNG格式）"""
        # 準備資料
        strategy_names = []
        total_returns = []
        annualized_returns = []
        sharpe_ratios = []
        max_drawdowns = []
        volatilities = []
        cumulative_returns = {}
        
        for name, result in self.results.items():
            strategy_names.append(name)
            metrics = result.get('metrics', {})
            total_returns.append(metrics.get('total_return', 0) * 100)
            annualized_returns.append(metrics.get('annualized_return', 0) * 100)
            sharpe_ratios.append(metrics.get('sharpe_ratio', 0))
            max_drawdowns.append(metrics.get('max_drawdown', 0) * 100)
            volatilities.append(metrics.get('volatility', 0) * 100)
            
            # 累積報酬率
            dates = result.get('dates', [])
            portfolio_values = result.get('portfolio_value', [])
            if dates and portfolio_values:
                initial_value = portfolio_values[0] if portfolio_values else 100000
                cumulative = [(v / initial_value - 1) * 100 for v in portfolio_values]
                cumulative_returns[name] = {
                    'dates': dates,
                    'returns': cumulative
                }
        
        # 建立圖表
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('所有策略績效比較', fontsize=16, fontweight='bold')
        
        # 1. 累積報酬率比較
        ax1 = axes[0, 0]
        for name, data in cumulative_returns.items():
            ax1.plot(data['dates'], data['returns'], label=name, linewidth=2)
        ax1.set_title('累積報酬率比較', fontsize=12, fontweight='bold')
        ax1.set_xlabel('日期')
        ax1.set_ylabel('累積報酬率 (%)')
        ax1.legend(loc='best', fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # 2. 年化報酬率比較
        ax2 = axes[0, 1]
        bars = ax2.bar(range(len(strategy_names)), annualized_returns, color='steelblue', alpha=0.7)
        ax2.set_title('年化報酬率比較', fontsize=12, fontweight='bold')
        ax2.set_xlabel('策略')
        ax2.set_ylabel('年化報酬率 (%)')
        ax2.set_xticks(range(len(strategy_names)))
        ax2.set_xticklabels(strategy_names, rotation=45, ha='right', fontsize=8)
        ax2.grid(True, alpha=0.3, axis='y')
        # 添加數值標籤
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}%', ha='center', va='bottom', fontsize=8)
        
        # 3. 夏普比率比較
        ax3 = axes[0, 2]
        bars = ax3.bar(range(len(strategy_names)), sharpe_ratios, color='green', alpha=0.7)
        ax3.set_title('夏普比率比較', fontsize=12, fontweight='bold')
        ax3.set_xlabel('策略')
        ax3.set_ylabel('夏普比率')
        ax3.set_xticks(range(len(strategy_names)))
        ax3.set_xticklabels(strategy_names, rotation=45, ha='right', fontsize=8)
        ax3.grid(True, alpha=0.3, axis='y')
        # 添加數值標籤
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=8)
        
        # 4. 最大回撤比較
        ax4 = axes[1, 0]
        bars = ax4.bar(range(len(strategy_names)), max_drawdowns, color='red', alpha=0.7)
        ax4.set_title('最大回撤比較', fontsize=12, fontweight='bold')
        ax4.set_xlabel('策略')
        ax4.set_ylabel('最大回撤 (%)')
        ax4.set_xticks(range(len(strategy_names)))
        ax4.set_xticklabels(strategy_names, rotation=45, ha='right', fontsize=8)
        ax4.grid(True, alpha=0.3, axis='y')
        # 添加數值標籤
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}%', ha='center', va='top', fontsize=8)
        
        # 5. 風險報酬散點圖
        ax5 = axes[1, 1]
        scatter = ax5.scatter(volatilities, annualized_returns, s=100, alpha=0.6, c=range(len(strategy_names)), cmap='viridis')
        for i, name in enumerate(strategy_names):
            ax5.annotate(name, (volatilities[i], annualized_returns[i]), 
                        fontsize=8, ha='center', va='bottom')
        ax5.set_title('風險報酬散點圖', fontsize=12, fontweight='bold')
        ax5.set_xlabel('波動度 (%)')
        ax5.set_ylabel('年化報酬率 (%)')
        ax5.grid(True, alpha=0.3)
        
        # 6. 績效指標總覽表
        ax6 = axes[1, 2]
        ax6.axis('tight')
        ax6.axis('off')
        table_data = []
        for i, name in enumerate(strategy_names):
            table_data.append([
                name,
                f'{total_returns[i]:.2f}%',
                f'{annualized_returns[i]:.2f}%',
                f'{sharpe_ratios[i]:.2f}',
                f'{max_drawdowns[i]:.2f}%',
                f'{volatilities[i]:.2f}%'
            ])
        table = ax6.table(cellText=table_data,
                         colLabels=['策略', '總報酬率', '年化報酬率', '夏普比率', '最大回撤', '波動度'],
                         cellLoc='center',
                         loc='center',
                         bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 2)
        ax6.set_title('績效指標總覽', fontsize=12, fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        # 儲存圖表
        output_path = os.path.join(output_dir, 'all_strategies_comparison.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"[Info] 已生成所有策略績效比較圖表：{output_path}")
    
    def _generate_comparison_html(self, output_dir):
        """生成所有策略績效比較圖表（HTML格式，互動式）"""
        # 準備資料
        strategy_names = []
        total_returns = []
        annualized_returns = []
        sharpe_ratios = []
        max_drawdowns = []
        volatilities = []
        cumulative_returns = {}
        
        for name, result in self.results.items():
            strategy_names.append(name)
            metrics = result.get('metrics', {})
            total_returns.append(metrics.get('total_return', 0) * 100)
            annualized_returns.append(metrics.get('annualized_return', 0) * 100)
            sharpe_ratios.append(metrics.get('sharpe_ratio', 0))
            max_drawdowns.append(metrics.get('max_drawdown', 0) * 100)
            volatilities.append(metrics.get('volatility', 0) * 100)
            
            # 累積報酬率
            dates = result.get('dates', [])
            portfolio_values = result.get('portfolio_value', [])
            if dates and portfolio_values:
                initial_value = portfolio_values[0] if portfolio_values else 100000
                cumulative = [(v / initial_value - 1) * 100 for v in portfolio_values]
                cumulative_returns[name] = {
                    'dates': dates,
                    'returns': cumulative
                }
        
        # 建立子圖
        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=('累積報酬率比較', '年化報酬率比較', '夏普比率比較',
                          '最大回撤比較', '風險報酬散點圖', '績效指標總覽'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}, {"type": "table"}]]
        )
        
        # 1. 累積報酬率比較
        for name, data in cumulative_returns.items():
            fig.add_trace(
                go.Scatter(x=data['dates'], y=data['returns'], mode='lines', name=name),
                row=1, col=1
            )
        
        # 2. 年化報酬率比較
        fig.add_trace(
            go.Bar(x=strategy_names, y=annualized_returns, name='年化報酬率',
                  text=[f'{r:.2f}%' for r in annualized_returns], textposition='outside'),
            row=1, col=2
        )
        
        # 3. 夏普比率比較
        fig.add_trace(
            go.Bar(x=strategy_names, y=sharpe_ratios, name='夏普比率',
                  text=[f'{s:.2f}' for s in sharpe_ratios], textposition='outside'),
            row=1, col=3
        )
        
        # 4. 最大回撤比較
        fig.add_trace(
            go.Bar(x=strategy_names, y=max_drawdowns, name='最大回撤',
                  text=[f'{d:.2f}%' for d in max_drawdowns], textposition='outside'),
            row=2, col=1
        )
        
        # 5. 風險報酬散點圖
        fig.add_trace(
            go.Scatter(x=volatilities, y=annualized_returns, mode='markers+text',
                      text=strategy_names, textposition='top center',
                      marker=dict(size=10, color=range(len(strategy_names)), colorscale='Viridis'),
                      name='風險報酬'),
            row=2, col=2
        )
        
        # 6. 績效指標總覽表
        table_data = []
        for i, name in enumerate(strategy_names):
            table_data.append([
                name,
                f'{total_returns[i]:.2f}%',
                f'{annualized_returns[i]:.2f}%',
                f'{sharpe_ratios[i]:.2f}',
                f'{max_drawdowns[i]:.2f}%',
                f'{volatilities[i]:.2f}%'
            ])
        fig.add_trace(
            go.Table(
                header=dict(values=['策略', '總報酬率', '年化報酬率', '夏普比率', '最大回撤', '波動度'],
                           fill_color='paleturquoise', align='center'),
                cells=dict(values=list(zip(*table_data)),
                          fill_color='lavender', align='center')
            ),
            row=2, col=3
        )
        
        # 更新佈局
        fig.update_layout(
            title_text='所有策略績效比較',
            height=1000,
            showlegend=True
        )
        
        # 更新座標軸標籤
        fig.update_xaxes(title_text='日期', row=1, col=1)
        fig.update_yaxes(title_text='累積報酬率 (%)', row=1, col=1)
        fig.update_xaxes(title_text='策略', row=1, col=2)
        fig.update_yaxes(title_text='年化報酬率 (%)', row=1, col=2)
        fig.update_xaxes(title_text='策略', row=1, col=3)
        fig.update_yaxes(title_text='夏普比率', row=1, col=3)
        fig.update_xaxes(title_text='策略', row=2, col=1)
        fig.update_yaxes(title_text='最大回撤 (%)', row=2, col=1)
        fig.update_xaxes(title_text='波動度 (%)', row=2, col=2)
        fig.update_yaxes(title_text='年化報酬率 (%)', row=2, col=2)
        
        # 儲存圖表
        output_path = os.path.join(output_dir, 'all_strategies_comparison.html')
        fig.write_html(output_path)
        
        print(f"[Info] 已生成所有策略績效比較圖表（互動式）：{output_path}")
    
    def _generate_detail_png(self, strategy_name, strategy_result, output_dir):
        """生成單一策略詳細分析圖表（PNG格式）"""
        # 這個方法會在後續實作
        pass
    
    def _generate_detail_html(self, strategy_name, strategy_result, output_dir):
        """生成單一策略詳細分析圖表（HTML格式）"""
        # 這個方法會在後續實作
        pass


