import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { CustomStrategies } from './custom-strategies';

const CATALOG = {
  SMA: [
    { name: 'short_period', label: 'Short average (days)', description: 'fast', kind: 'int', default: 5, min: 2, max: 100 },
    { name: 'long_period', label: 'Long average (days)', description: 'slow', kind: 'int', default: 20, min: 3, max: 400 },
  ],
  RSI: [
    { name: 'period', label: 'RSI period (days)', description: 'p', kind: 'int', default: 14, min: 2, max: 100 },
    { name: 'oversold', label: 'Oversold limit', description: 'o', kind: 'float', default: 30, min: 1, max: 49 },
    { name: 'overbought', label: 'Overbought limit', description: 'b', kind: 'float', default: 70, min: 51, max: 99 },
  ],
  BOLLINGER: [],
  MOMENTUM: [],
};

describe('CustomStrategies (US-21)', () => {
  let fixture: ComponentFixture<CustomStrategies>;
  let component: CustomStrategies;
  let http: HttpTestingController;
  const html = () => fixture.nativeElement as HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomStrategies],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(CustomStrategies);
    component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne((r) => r.url.endsWith('/custom-strategies/parameters')).flush(CATALOG);
    http.expectOne((r) => r.url.endsWith('/custom-strategies') && r.method === 'GET').flush([]);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('draws one input per parameter with the default values', () => {
    const inputs = html().querySelectorAll<HTMLInputElement>('.param input');
    expect(Array.from(inputs).map((i) => i.value)).toEqual(['5', '20']);
  });

  it('rebuilds the inputs when the base strategy changes', () => {
    component.form.controls.base.setValue('RSI');
    component.onBaseChange();
    fixture.detectChanges();

    const inputs = html().querySelectorAll<HTMLInputElement>('.param input');
    expect(Array.from(inputs).map((i) => i.value)).toEqual(['14', '30', '70']);
  });

  it('lists every problem the server finds at once and does not claim the strategy is valid', () => {
    component.form.controls.name.setValue('Broken');
    component.form.controls.params.get('short_period')!.setValue(50);
    component.check();

    http.expectOne((r) => r.url.endsWith('/custom-strategies/validate')).flush(
      { detail: ['The short average must be shorter than the long average', 'Another problem'] },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(Array.from(html().querySelectorAll('.problems li')).map((li) => li.textContent)).toEqual([
      'The short average must be shorter than the long average',
      'Another problem',
    ]);
    expect(html().querySelector('.ok')).toBeNull();
  });

  it('saves the typed name and numbers, then clears the form', () => {
    component.form.controls.name.setValue('  Fast SMA ');
    component.form.controls.params.get('short_period')!.setValue(3);
    component.form.controls.params.get('long_period')!.setValue(12);
    component.save();

    const create = http.expectOne((r) => r.url.endsWith('/custom-strategies') && r.method === 'POST');
    expect(create.request.body).toEqual({ name: 'Fast SMA', base_strategy: 'SMA', params: { short_period: 3, long_period: 12 } });
    create.flush({});
    http.expectOne((r) => r.url.endsWith('/custom-strategies') && r.method === 'GET').flush([]);

    expect(component.form.controls.name.value).toBe('');
    expect(component.editingId()).toBeNull();
  });

  it('does not call the server with an invalid name', () => {
    component.form.controls.name.setValue('ab');
    component.save();
    http.expectNone((r) => r.method === 'POST');
  });

  it('edits an existing strategy and saves it with PUT', () => {
    component.edit({
      id: 'abc', name: 'Patient RSI', base_strategy: 'RSI', params: { period: 21, oversold: 25, overbought: 75 },
      created_at: '', updated_at: '',
    });
    expect(component.form.controls.params.get('period')!.value).toBe(21);

    component.form.controls.params.get('period')!.setValue(9);
    component.save();
    const update = http.expectOne((r) => r.url.endsWith('/custom-strategies/abc') && r.method === 'PUT');
    expect(update.request.body.params.period).toBe(9);
    update.flush({});
    http.expectOne((r) => r.url.endsWith('/custom-strategies') && r.method === 'GET').flush([]);
  });
});
