import { describe, expect, it } from 'vitest';

import { ApiError, messageForCode, toUserMessage } from './errors';

describe('messageForCode', () => {
  it('returns friendly copy for a known code', () => {
    expect(messageForCode('RATE_LIMITED')).toContain('going a bit fast');
  });

  it('falls back to a generic message for an unknown code', () => {
    expect(messageForCode('SOMETHING_NEW')).toBe(messageForCode('INTERNAL_ERROR'));
  });

  it('prefers a supplied fallback over the generic message', () => {
    expect(messageForCode('SOMETHING_NEW', 'Custom explanation')).toBe('Custom explanation');
  });
});

describe('ApiError.fromResponse', () => {
  it('reads code, message, and details out of the error envelope', async () => {
    const response = new Response(
      JSON.stringify({
        error: {
          code: 'CONFLICT',
          message: 'Email already registered.',
          details: [{ field: 'email', issue: 'already in use' }],
          correlation_id: 'abc-123',
        },
      }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    );

    const error = await ApiError.fromResponse(response);

    expect(error.code).toBe('CONFLICT');
    expect(error.status).toBe(409);
    expect(error.details).toEqual([{ field: 'email', issue: 'already in use' }]);
    expect(error.correlationId).toBe('abc-123');
  });

  it('still produces a usable error when the body is not JSON', async () => {
    // A proxy timeout or a crash before our handlers run can return HTML. The
    // client must not fail on top of the failure it is trying to report.
    const response = new Response('<html>502 Bad Gateway</html>', { status: 502 });

    const error = await ApiError.fromResponse(response);

    expect(error.status).toBe(502);
    expect(error.code).toBe('INTERNAL_ERROR');
    expect(error.userMessage).toBeTruthy();
  });

  it('treats a 401 as an expired session so the client can refresh', async () => {
    const response = new Response(JSON.stringify({ error: { code: 'TOKEN_EXPIRED', message: '' } }), {
      status: 401,
    });

    const error = await ApiError.fromResponse(response);

    expect(error.isAuthExpired).toBe(true);
  });
});

describe('toUserMessage', () => {
  it('uses the mapped copy for an ApiError', () => {
    const error = new ApiError({ code: 'NOT_FOUND', message: 'raw internal text', status: 404 });

    expect(toUserMessage(error)).toBe(messageForCode('NOT_FOUND'));
  });

  it('never exposes a raw thrown value', () => {
    expect(toUserMessage(new Error('connection refused at 10.0.0.5:5432'))).not.toContain('10.0.0.5');
  });
});
