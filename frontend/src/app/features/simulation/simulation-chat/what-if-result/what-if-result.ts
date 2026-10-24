import { Component, computed, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';

import { WhatIfResult as Result } from '@models/agent/what-if.model';

const KEY_METRICS = ['total_return_pct', 'final_value', 'max_drawdown_pct', 'sharpe_ratio'];

/** Summary of a what-if (US-28): the original run against the copy, or the qualitative fallback. */
@Component({
  selector: 'app-what-if-result',
  imports: [RouterLink],
  templateUrl: './what-if-result.html',
  styleUrl: './what-if-result.css',
})
export class WhatIfResult {
  result = input.required<Result>();
  closed = output<void>();

  metrics = computed(() =>
    (this.result().comparison?.metrics_diff ?? []).filter(m => KEY_METRICS.includes(m.metric)),
  );
}
