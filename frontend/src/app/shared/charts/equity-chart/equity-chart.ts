import {
  AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, ViewChild
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import {
  createChart, ColorType, CrosshairMode, LineStyle,
  IChartApi, ISeriesApi, IPriceLine, MouseEventParams, SeriesMarker, Time
} from 'lightweight-charts';
import { EquityPoint } from '@models/analysis/equity-point.model';
import { Trade } from '@models/analysis/trade.model';

/** Agent highlight drawn on the curve (e.g. the peak and low of the largest drop). */
export interface ChartHighlight {
  date: string;
  text: string;
}

interface HoverInfo {
  date: string;
  value: number;
  changePct: number;
  trade: Trade | undefined;
  left: number;
}

@Component({
  selector: 'app-equity-chart',
  imports: [DecimalPipe],
  templateUrl: './equity-chart.html',
  styleUrl: './equity-chart.css',
})
export class EquityChart implements AfterViewInit, OnChanges, OnDestroy {
  @Input() equityCurve: EquityPoint[] = [];
  @Input() trades: Trade[] = [];
  @Input() initialCapital: number | null = null;
  @Input() highlights: ChartHighlight[] = [];

  @ViewChild('chartContainer') private container!: ElementRef<HTMLDivElement>;

  hover: HoverInfo | null = null;

  private chart: IChartApi | null = null;
  private series: ISeriesApi<'Area'> | null = null;
  private baseline: IPriceLine | null = null;

  ngAfterViewInit(): void {
    this.chart = createChart(this.container.nativeElement, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8FA6B5',
        fontFamily: 'Inter, sans-serif',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: 'rgba(245, 243, 238, 0.06)' },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: CrosshairMode.Magnet },
    });

    this.series = this.chart.addAreaSeries({
      lineColor: '#C9A15C',
      topColor: 'rgba(201, 161, 92, 0.28)',
      bottomColor: 'rgba(201, 161, 92, 0.02)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    this.chart.subscribeCrosshairMove(this.onCrosshairMove);
    this.render();
  }

  ngOnChanges(): void {
    this.render();
  }

  ngOnDestroy(): void {
    if (this.chart) {
      this.chart.unsubscribeCrosshairMove(this.onCrosshairMove);
      this.chart.remove();
      this.chart = null;
    }
  }

  get startPoint(): EquityPoint | undefined {
    return this.equityCurve[0];
  }

  get endPoint(): EquityPoint | undefined {
    return this.equityCurve[this.equityCurve.length - 1];
  }

  private render(): void {
    if (!this.chart || !this.series) return;

    this.series.setData(
      this.equityCurve.map(e => ({ time: e.date as Time, value: e.portfolio_value }))
    );

    // Trade markers: shape + text, not color alone. Must be sorted by time.
    const tradeMarkers: SeriesMarker<Time>[] = this.trades.map(t => t.type === 'BUY'
      ? { time: t.date as Time, position: 'belowBar', color: '#2ECC91', shape: 'arrowUp', text: 'BUY' }
      : { time: t.date as Time, position: 'aboveBar', color: '#E0605E', shape: 'arrowDown', text: 'SELL' });
    const highlightMarkers: SeriesMarker<Time>[] = this.highlights.map(h => (
      { time: h.date as Time, position: 'inBar', color: '#C9A15C', shape: 'circle', text: h.text }
    ));
    const markers = [...tradeMarkers, ...highlightMarkers]
      .sort((a, b) => (a.time as string).localeCompare(b.time as string));
    this.series.setMarkers(markers);

    // Reference line at the initial capital, so the start level is always visible.
    if (this.baseline) {
      this.series.removePriceLine(this.baseline);
      this.baseline = null;
    }
    if (this.initialCapital !== null) {
      this.baseline = this.series.createPriceLine({
        price: this.initialCapital,
        color: 'rgba(245, 243, 238, 0.35)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'Initial',
      });
    }

    this.chart.timeScale().fitContent();
  }

  // Arrow function so `this` stays bound when lightweight-charts calls it.
  private onCrosshairMove = (param: MouseEventParams<Time>): void => {
    if (!this.series || !param.time || !param.point) {
      this.hover = null;
      return;
    }
    const data = param.seriesData.get(this.series) as { value: number } | undefined;
    if (!data) {
      this.hover = null;
      return;
    }
    const date = param.time as string;
    const base = this.initialCapital ?? this.startPoint?.portfolio_value ?? data.value;
    this.hover = {
      date,
      value: data.value,
      changePct: base ? ((data.value / base) - 1) * 100 : 0,
      trade: this.trades.find(t => t.date === date),
      left: param.point.x,
    };
  };
}