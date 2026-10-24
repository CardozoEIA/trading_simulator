import { Component, inject, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Simulations } from '@core/api/simulations';
import { Alert } from '@shared/ui/alert/alert';
import { SimulationHistoryItem } from '@models/simulation/simulation-history.model';

@Component({
  selector: 'app-simulation-history',
  imports: [RouterLink, DecimalPipe, DatePipe],
  templateUrl: './simulation-history.html',
  styleUrl: './simulation-history.css',
})
export class SimulationHistory implements OnInit {
  private simulations = inject(Simulations);
  private alert = inject(Alert);
  private router = inject(Router);

  history: SimulationHistoryItem[] = [];
  loading = true;

  ngOnInit(): void {
    this.simulations.getHistory().subscribe({
      next: (response) => { this.history = response; this.loading = false; },
      error: (error) => { this.alert.showApiError(error); this.loading = false; }
    });
  }

  open(item: SimulationHistoryItem): void {
    if (item.status === 'RUNNING') {
      this.router.navigate(['/simulation-status', item.id]);
    } else {
      this.router.navigate(['/simulation-decisions', item.id]);
    }
  }

  // --- Compare two simulations (US-27) ---
  selected: string[] = [];

  isSelected(item: SimulationHistoryItem): boolean {
    return this.selected.includes(item.id);
  }

  canSelect(item: SimulationHistoryItem): boolean {
    return item.status !== 'RUNNING' && (this.isSelected(item) || this.selected.length < 2);
  }

  toggleSelection(item: SimulationHistoryItem): void {
    this.selected = this.isSelected(item)
      ? this.selected.filter(id => id !== item.id)
      : [...this.selected, item.id];
  }

  compare(): void {
    if (this.selected.length !== 2) return;
    // A is the older run, so "B minus A" reads as what changed in the newer one
    const [a, b] = this.history
      .filter(h => this.selected.includes(h.id))
      .sort((x, y) => x.started_at.localeCompare(y.started_at));
    this.router.navigate(['/compare'], { queryParams: { a: a.id, b: b.id } });
  }

  statusLabel(status: string): string {
    if (status === 'FINISHED') return 'Completed';
    if (status === 'STOPPED_BY_RISK') return 'Stopped by risk';
    return 'Running';
  }
}