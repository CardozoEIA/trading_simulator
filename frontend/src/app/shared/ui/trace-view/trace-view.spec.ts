import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TraceView } from './trace-view';

describe('TraceView (US-31)', () => {
  let fixture: ComponentFixture<TraceView>;

  const trace = [
    { tool: 'get_decision', arguments: { date: '2023-10-05' }, result: 'Action: BUY | Executed: True' },
    { tool: 'get_indicators', arguments: { date: '2023-10-05' }, result: 'RSI: 28.41' },
  ];

  const text = () => (fixture.nativeElement as HTMLElement).textContent ?? '';
  const toggle = () => (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.trace-toggle')!;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TraceView] }).compileComponents();
    fixture = TestBed.createComponent(TraceView);
  });

  it('is closed by default and shows every tool call with its value once opened', () => {
    fixture.componentRef.setInput('trace', trace);
    fixture.componentRef.setInput('verification', { verified: true, tools_called: 2, removed: [] });
    fixture.detectChanges();

    expect(toggle().getAttribute('aria-expanded')).toBe('false');
    expect(text()).not.toContain('RSI: 28.41');

    toggle().click();
    fixture.detectChanges();

    expect(text()).toContain('get_decision');
    expect(text()).toContain('date: 2023-10-05');
    expect(text()).toContain('RSI: 28.41');
    expect(text()).toContain('every date and number in the answer was found');
  });

  it('shows which statements the self-check removed and why', () => {
    fixture.componentRef.setInput('trace', trace);
    fixture.componentRef.setInput('verification', {
      verified: false,
      tools_called: 2,
      removed: [{ statement: 'The RSI was 71.9 a week earlier.', problems: ['71.9'] }],
    });
    fixture.detectChanges();
    toggle().click();
    fixture.detectChanges();

    expect(text()).toContain('1 removed');
    expect(text()).toContain('The RSI was 71.9 a week earlier.');
    expect(text()).toContain('not backed: 71.9');
  });

  it('says so when the agent used no tool', () => {
    fixture.componentRef.setInput('trace', []);
    fixture.detectChanges();
    toggle().click();
    fixture.detectChanges();

    expect(text()).toContain('did not call any tool');
  });
});
