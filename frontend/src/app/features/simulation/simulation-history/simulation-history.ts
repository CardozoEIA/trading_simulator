import { Component, inject, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { catchError, forkJoin, map, of } from 'rxjs';
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

  // --- Selection: compare exactly two, delete any number ---
  selected: string[] = [];
  deleting = false;

  get selectable(): SimulationHistoryItem[] {
    return this.history.filter(h => h.status !== 'RUNNING');
  }

  get allSelected(): boolean {
    return this.selectable.length > 0 && this.selected.length === this.selectable.length;
  }

  get canCompare(): boolean {
    return this.selected.length === 2 && !this.deleting;
  }

  get selectionHint(): string {
    const count = this.selected.length;
    if (count === 0) return 'Select simulations to compare (two) or delete (any number).';
    if (count === 1) return '1 selected · select one more to compare.';
    if (count === 2) return '2 selected · ready to compare.';
    return `${count} selected · compare works with exactly two.`;
  }

  isSelected(item: SimulationHistoryItem): boolean {
    return this.selected.includes(item.id);
  }

  toggleSelection(item: SimulationHistoryItem): void {
    this.selected = this.isSelected(item)
      ? this.selected.filter(id => id !== item.id)
      : [...this.selected, item.id];
  }

  toggleAll(): void {
    this.selected = this.allSelected ? [] : this.selectable.map(h => h.id);
  }

  compare(): void {
    if (!this.canCompare) return;
    // A is the older run, so "B minus A" reads as what changed in the newer one
    const [a, b] = this.history
      .filter(h => this.selected.includes(h.id))
      .sort((x, y) => x.started_at.localeCompare(y.started_at));
    this.router.navigate(['/compare'], { queryParams: { a: a.id, b: b.id } });
  }

  async deleteSelected(): Promise<void> {
    const ids = [...this.selected];
    if (ids.length === 0 || this.deleting) return;
    const what = ids.length === 1 ? 'this simulation' : `these ${ids.length} simulations`;
    const confirmed = await this.alert.confirm(
      `Delete ${what}? Their results, decisions and chat will be removed. This cannot be undone.`,
    );
    if (!confirmed) return;

    this.deleting = true;
    // One request per simulation; a failure does not stop the others.
    forkJoin(ids.map(id => this.simulations.deleteSimulation(id).pipe(
      map(() => ({ id, error: null as unknown })),
      catchError(error => of({ id, error: error as unknown })),
    ))).subscribe(results => {
      const deleted = new Set(results.filter(r => !r.error).map(r => r.id));
      this.history = this.history.filter(h => !deleted.has(h.id));
      this.selected = this.selected.filter(id => !deleted.has(id));
      this.deleting = false;

      const failed = results.filter(r => r.error);
      if (failed.length) {
        this.alert.showError(
          `${failed.length} of ${ids.length} simulation(s) could not be deleted. They are still selected; try again.`,
        );
      }
    });
  }

  statusLabel(status: string): string {
    if (status === 'FINISHED') return 'Completed';
    if (status === 'STOPPED_BY_RISK') return 'Stopped by risk';
    return 'Running';
  }
}
