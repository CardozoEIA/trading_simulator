import { Component, inject, OnInit } from '@angular/core';
import { Backtest } from '../../core/backtest';
import { Asset } from '../../models/asset.model';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { Alert } from '../../shared/alert';
import { Router, RouterLink } from '@angular/router';
import { BacktestConfigurationResponse } from '../../models/backtest-configuration-response.model';
import { AbstractControl, ValidationErrors } from '@angular/forms';
import { StepIndicator } from '../../shared/step-indicator/step-indicator';

@Component({
  selector: 'app-simulation-config',
  imports: [ ReactiveFormsModule, RouterLink, StepIndicator ],
  templateUrl: './simulation-config.html',
  styleUrl: './simulation-config.css',
})

export class SimulationConfig implements OnInit {

  private backtest = inject(Backtest);
  private alert = inject(Alert);
  private router = inject(Router)
  savedConfig: BacktestConfigurationResponse | null = null;
  assets: Asset[] = [];
  submitted = false;

  simConfigForm = new FormGroup({
    asset: new FormControl('', Validators.required),
    startDate: new FormControl('', Validators.required),
    endDate: new FormControl('', Validators.required),
    initialCapital: new FormControl<number | null>(null, [Validators.required, Validators.min(1)]),
    strategy: new FormControl('', Validators.required)
  }, { validators: dateRangeValidator });

  ngOnInit(): void {
    this.backtest.getAssets().subscribe({
      next: (response) => { this.assets = response },
      error: (error) => { console.log(error)}
    })
  }

  onSubmit(){
    this.submitted = true;

    if (this.simConfigForm.invalid) {
      return;
    }

    this.backtest.configureBacktest(
      this.simConfigForm.value.asset ?? '',
      this.simConfigForm.value.startDate ?? '',
      this.simConfigForm.value.endDate ?? '',
      this.simConfigForm.value.initialCapital ?? 0,
      this.simConfigForm.value.strategy ?? ''
    ).subscribe({
      next: (response) => {
        this.savedConfig = response;
        this.router.navigate(['/risk-config', response.id]);
      },
      error: (error) => { this.alert.showApiError(error) }
    })
  }
}

function dateRangeValidator(group: AbstractControl): ValidationErrors | null {
    const start = group.get('startDate')?.value;
    const end = group.get('endDate')?.value;

    if (start && end && start >= end) {
      return { dateRangeInvalid: true };
    }
    return null;
  }