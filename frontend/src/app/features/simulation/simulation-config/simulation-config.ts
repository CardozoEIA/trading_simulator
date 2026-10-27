import { Component, inject, OnInit } from '@angular/core';
import { Backtest } from '@core/api/backtest';
import { Asset } from '@models/simulation/asset.model';
import { Strategy } from '@models/simulation/strategy.model';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, FormArray, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Alert } from '@shared/ui/alert/alert';
import { Router, RouterLink } from '@angular/router';
import { BacktestConfigurationResponse } from '@models/simulation/backtest-configuration-response.model';
import { StepIndicator } from '@shared/ui/step-indicator/step-indicator';
import { HelpHint } from '@shared/ui/help-hint/help-hint';
import { PENDING_RISK_CHANGE_KEY } from '@models/agent/chat.model';
import { PENDING_SETUP_RISK_KEY, SetupProposal } from '@models/agent/setup.model';
import { DescribeSetup } from './describe-setup/describe-setup';

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
  imports: [ReactiveFormsModule, RouterLink, StepIndicator, HelpHint, DescribeSetup],
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
    strategies: new FormArray([] as FormControl[], atLeastOneStrategyValidator),
    // US-24: only used when two or more strategies are combined. Empty = the default (0.1).
    ensembleThreshold: new FormControl<number | null>(null, [Validators.min(0.01), Validators.max(1)])
  }, { validators: dateRangeValidator });

  get strategiesArray(): FormArray {
    return this.simConfigForm.get('strategies') as FormArray;
  }

  /** How many strategies are ticked right now (decides whether the ensemble threshold applies). */
  get selectedCount(): number {
    return this.strategiesArray.controls.filter(c => c.value === true).length;
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

  /** US-29: a proposal the student confirmed only pre-fills the form; they still review and submit it. */
  applyDescribedSetup(proposal: SetupProposal): void {
    this.simConfigForm.patchValue({
      asset: proposal.asset ?? '',
      startDate: proposal.start_date ?? '',
      endDate: proposal.end_date ?? '',
      initialCapital: proposal.initial_capital,
    });
    this.strategies.forEach((strategy, index) =>
      this.strategiesArray.at(index).setValue((proposal.strategies ?? []).includes(strategy.code)));

    try {
      sessionStorage.removeItem(PENDING_RISK_CHANGE_KEY);
      sessionStorage.setItem(PENDING_SETUP_RISK_KEY, JSON.stringify({
        stop_loss_percentage: proposal.stop_loss_percentage,
        max_position_size: proposal.max_position_size,
        max_drawdown: proposal.max_drawdown,
        createdAt: Date.now(),
      }));
    } catch {
      // Without storage the risk step simply opens empty.
    }
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
      selectedStrategies,
      this.selectedCount >= 2 ? (this.simConfigForm.value.ensembleThreshold ?? null) : null
    ).subscribe({
      next: (response) => {
        this.savedConfig = response;
        this.router.navigate(['/risk-config', response.id]);
      },
      error: (error) => { this.alert.showApiError(error) }
    });
  }
}