import { Component, inject, OnInit } from '@angular/core';
import { Backtest } from '../../core/backtest';
import { Asset } from '../../models/asset.model';
import { Strategy } from '../../models/strategy.model';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, FormArray, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Alert } from '../../shared/alert';
import { Router } from '@angular/router';
import { BacktestConfigurationResponse } from '../../models/backtest-configuration-response.model';
import { StepIndicator } from '../../shared/step-indicator/step-indicator';

function dateRangeValidator(group: AbstractControl): ValidationErrors | null {
  const start = group.get('startDate')?.value;
  const end = group.get('endDate')?.value;
  if (start && end && start >= end) {
    return { dateRangeInvalid: true };
  }
  return null;
}

function atLeastOneStrategyValidator(control: AbstractControl): ValidationErrors | null {
  const array = control as FormArray;
  const anyChecked = array.controls.some(c => c.value === true);
  return anyChecked ? null : { noStrategySelected: true };
}

@Component({
  selector: 'app-simulation-config',
  imports: [ReactiveFormsModule, StepIndicator],
  templateUrl: './simulation-config.html',
  styleUrl: './simulation-config.css',
})
export class SimulationConfig implements OnInit {

  private backtest = inject(Backtest);
  private alert = inject(Alert);
  private router = inject(Router);

  savedConfig: BacktestConfigurationResponse | null = null;
  assets: Asset[] = [];
  strategies: Strategy[] = [];
  submitted = false;

  simConfigForm = new FormGroup({
    asset: new FormControl('', Validators.required),
    startDate: new FormControl('', Validators.required),
    endDate: new FormControl('', Validators.required),
    initialCapital: new FormControl<number | null>(null, [Validators.required, Validators.min(1)]),
    strategies: new FormArray([] as FormControl[], atLeastOneStrategyValidator)
  }, { validators: dateRangeValidator });

  get strategiesArray(): FormArray {
    return this.simConfigForm.get('strategies') as FormArray;
  }

  async onDashboardClick() {
    const confirmed = await this.alert.confirmLeaveWizard();
    if (confirmed) {
      this.router.navigate(['/dashboard']);
    }
  }

  ngOnInit(): void {
    this.backtest.getAssets().subscribe({
      next: (response) => { this.assets = response },
      error: (error) => { this.alert.showApiError(error) }
    });

    this.backtest.getStrategies().subscribe({
      next: (response) => {
        this.strategies = response;
        response.forEach(() => this.strategiesArray.push(new FormControl(false)));
      },
      error: (error) => { this.alert.showApiError(error) }
    });
  }

  onSubmit(){
    this.submitted = true;

    if (this.simConfigForm.invalid) {
      return;
    }

    const selectedStrategies = this.strategies
      .filter((_, index) => this.strategiesArray.at(index).value === true)
      .map(s => s.code);

    this.backtest.configureBacktest(
      this.simConfigForm.value.asset ?? '',
      this.simConfigForm.value.startDate ?? '',
      this.simConfigForm.value.endDate ?? '',
      this.simConfigForm.value.initialCapital ?? 0,
      selectedStrategies
    ).subscribe({
      next: (response) => {
        this.savedConfig = response;
        this.router.navigate(['/risk-config', response.id]);
      },
      error: (error) => { this.alert.showApiError(error) }
    });
  }
}