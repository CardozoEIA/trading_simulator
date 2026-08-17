import { Component, inject, OnInit } from '@angular/core';
import { Backtest } from '../../core/backtest';
import { Asset } from '../../models/asset.model';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { Alert } from '../../shared/alert';
import { RouterLink } from '@angular/router';
import { BacktestConfigurationResponse } from '../../models/backtest-configuration-response.model';
import { AbstractControl, ValidationErrors } from '@angular/forms';

@Component({
  selector: 'app-simulation-config',
  imports: [ ReactiveFormsModule, RouterLink ],
  templateUrl: './simulation-config.html',
  styleUrl: './simulation-config.css',
})

export class SimulationConfig implements OnInit {

  private backtest = inject(Backtest);
  private alert = inject(Alert);
  savedConfig: BacktestConfigurationResponse | null = null;
  assets: Asset[] = []; // no puede ser private, el html debe acceder a ella

  simConfigForm = new FormGroup({
    asset: new FormControl('', Validators.required),
    startDate: new FormControl('', Validators.required),
    endDate: new FormControl('', Validators.required)
  }, { validators: dateRangeValidator });

  ngOnInit(): void {
    this.backtest.getAssets().subscribe({
      next: (response) => { this.assets = response },
      error: (error) => { console.log(error)}
    })
  }

  onSubmit(){
    this.backtest.configureBacktest(this.simConfigForm.value.asset ?? '',
      this.simConfigForm.value.startDate ?? '',
      this.simConfigForm.value.endDate ?? '').subscribe({

        next: (response) => { this.savedConfig = response;
          this.alert.showSuccess("Simulation configured succesfully!") },
        error: (error) => { this.alert.showError(error.error.detail) }
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