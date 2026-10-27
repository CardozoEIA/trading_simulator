import { Component, inject, OnInit, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, UntypedFormGroup, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { CustomStrategies as CustomStrategiesApi } from '@core/api/custom-strategies';
import {
  BaseStrategy,
  CustomStrategy,
  CustomStrategyInput,
  ParameterCatalog,
  ParameterSpec,
} from '@models/simulation/custom-strategy.model';
import { Alert } from '@shared/ui/alert/alert';

// Code first, as everywhere else in the app (SMA, RSI...), then the full name.
const BASE_NAMES: Record<BaseStrategy, string> = {
  SMA: 'SMA · Moving Average Crossover',
  RSI: 'RSI · Relative Strength Index',
  BOLLINGER: 'BOLLINGER · Bollinger Bands',
  MOMENTUM: 'MOMENTUM · Momentum',
};

/** US-21: create, modify, save and delete custom strategies (a base strategy with your own parameters). */
@Component({
  selector: 'app-custom-strategies',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './custom-strategies.html',
  styleUrl: './custom-strategies.css',
})
export class CustomStrategies implements OnInit {
  private api = inject(CustomStrategiesApi);
  private alert = inject(Alert);

  readonly bases = Object.keys(BASE_NAMES) as BaseStrategy[];
  readonly baseNames = BASE_NAMES;

  catalog = signal<ParameterCatalog | null>(null);
  strategies = signal<CustomStrategy[]>([]);
  editingId = signal<string | null>(null);   // null = creating a new one
  problems = signal<string[]>([]);           // what the server found wrong, all at once
  checked = signal(false);                   // the last "Check" found nothing wrong
  saving = signal(false);

  form = new FormGroup({
    name: new FormControl('', [Validators.required, Validators.minLength(3), Validators.maxLength(40)]),
    base: new FormControl<BaseStrategy>('SMA', { nonNullable: true }),
    // One number input per parameter of the chosen base strategy; rebuilt whenever the base changes.
    params: new UntypedFormGroup({}),
  });

  ngOnInit(): void {
    this.api.getParameters().subscribe({
      next: (catalog) => {
        this.catalog.set(catalog);
        this.resetForm();
      },
      error: (error) => this.alert.showApiError(error),
    });
    this.reload();
  }

  get paramSpecs(): ParameterSpec[] {
    return this.catalog()?.[this.form.controls.base.value] ?? [];
  }

  private reload(): void {
    this.api.list().subscribe({
      next: (list) => this.strategies.set(list),
      error: (error) => this.alert.showApiError(error),
    });
  }

  /** Rebuilds the parameter inputs for a base strategy, using the given values or the defaults. */
  private buildParams(base: BaseStrategy, values: Record<string, number> = {}): void {
    const group = this.form.controls.params;
    Object.keys(group.controls).forEach((name) => group.removeControl(name));
    for (const spec of this.catalog()?.[base] ?? []) {
      group.addControl(
        spec.name,
        new FormControl<number | null>(values[spec.name] ?? spec.default, [
          Validators.required,
          Validators.min(spec.min),
          Validators.max(spec.max),
        ]),
      );
    }
  }

  onBaseChange(): void {
    this.buildParams(this.form.controls.base.value);
    this.clearFeedback();
  }

  resetForm(): void {
    this.editingId.set(null);
    this.form.controls.name.setValue('');
    this.form.controls.base.setValue('SMA');
    this.buildParams('SMA');
    this.form.markAsUntouched();
    this.clearFeedback();
  }

  edit(strategy: CustomStrategy): void {
    this.editingId.set(strategy.id);
    this.form.controls.name.setValue(strategy.name);
    this.form.controls.base.setValue(strategy.base_strategy);
    this.buildParams(strategy.base_strategy, strategy.params);
    this.clearFeedback();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  restoreDefaults(): void {
    this.buildParams(this.form.controls.base.value);
    this.clearFeedback();
  }

  private clearFeedback(): void {
    this.problems.set([]);
    this.checked.set(false);
  }

  private payload(): CustomStrategyInput {
    const params: Record<string, number> = {};
    for (const [name, control] of Object.entries(this.form.controls.params.controls)) {
      params[name] = Number(control.value);
    }
    return { name: (this.form.controls.name.value ?? '').trim(), base_strategy: this.form.controls.base.value, params };
  }

  /** Validation happens on the server so the rules are written once; every problem comes back together. */
  check(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.api.validate(this.payload()).subscribe({
      next: () => {
        this.problems.set([]);
        this.checked.set(true);
      },
      error: (error) => this.showProblems(error),
    });
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    const id = this.editingId();
    const strategy = this.payload();
    const request = id ? this.api.update(id, strategy) : this.api.create(strategy);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.resetForm();
        this.reload();
        this.alert.showSuccess(
          id ? `"${strategy.name}" was updated.` : `"${strategy.name}" was created. You can now pick it when you configure a simulation.`,
        );
      },
      error: (error) => {
        this.saving.set(false);
        this.showProblems(error);
      },
    });
  }

  async remove(strategy: CustomStrategy): Promise<void> {
    const confirmed = await this.alert.confirm(
      `Delete "${strategy.name}"? Simulations that already used it keep their results.`,
    );
    if (!confirmed) return;
    this.api.remove(strategy.id).subscribe({
      next: () => {
        if (this.editingId() === strategy.id) this.resetForm();
        this.reload();
      },
      error: (error) => this.alert.showApiError(error),
    });
  }

  private showProblems(error: { status?: number; error?: { detail?: unknown } }): void {
    const detail = error?.error?.detail;
    this.checked.set(false);
    if (error?.status === 422 && Array.isArray(detail)) {
      this.problems.set(detail.map(String));
    } else if (typeof detail === 'string') {
      this.problems.set([detail]);
    } else {
      this.alert.showApiError(error);
    }
  }

  summary(strategy: CustomStrategy): string {
    const specs = this.catalog()?.[strategy.base_strategy] ?? [];
    return specs.map((spec) => `${spec.label.split(' (')[0]} ${strategy.params[spec.name]}`).join(' · ');
  }
}
