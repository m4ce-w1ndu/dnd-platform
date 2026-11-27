import { describe, expect, it } from 'vitest';

import { comandoTiro, d20, espressionePool, mod, modoDi, sg } from './dadi';

describe('dadi', () => {
  it('compone il vassoio', () => {
    expect(espressionePool({}, 0, '')).toBe('');
    expect(espressionePool({ 6: 2 }, 3, '')).toBe('2d6+3');
    expect(espressionePool({ 20: 1 }, -1, 'adv')).toBe('2d20kh1-1');
    expect(espressionePool({ 20: 1 }, 0, 'dis')).toBe('2d20kl1');
    expect(espressionePool({ 20: 2, 4: 0 }, 0, 'adv')).toBe('2d20');
  });

  it('d20 con vantaggio e bonus', () => {
    expect(d20(0, '')).toBe('1d20');
    expect(d20(5, 'adv')).toBe('2d20kh1+5');
    expect(d20(-2, 'dis')).toBe('2d20kl1-2');
    expect(modoDi('2d20kh1+5')).toBe('vantaggio');
    expect(modoDi('1d20')).toBe('');
  });

  it('modificatori e segni', () => {
    expect(mod(10)).toBe(0);
    expect(mod(15)).toBe(2);
    expect(mod(7)).toBe(-2);
    expect(sg(3)).toBe('+3');
    expect(sg(-2)).toBe('−2');
  });

  it('comando /r in chat', () => {
    expect(comandoTiro('/r 2d6+3')).toBe('2d6+3');
    expect(comandoTiro('/ROLL d%')).toBe('d%');
    expect(comandoTiro('ciao /r 1d4')).toBeNull();
  });
});
