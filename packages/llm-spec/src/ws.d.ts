declare module 'ws' {
  import { EventEmitter } from 'node:events';
  import type { ClientRequest, IncomingMessage } from 'node:http';
  import type { Duplex } from 'node:stream';

  export type RawData = string | Buffer | ArrayBuffer | Buffer[];

  export interface ClientOptions {
    headers?: Record<string, string>;
  }

  export interface SendOptions {
    binary?: boolean;
  }

  export default class WebSocket extends EventEmitter {
    static readonly CONNECTING: 0;
    static readonly OPEN: 1;
    static readonly CLOSING: 2;
    static readonly CLOSED: 3;

    readonly readyState: number;

    constructor(
      address: string | URL,
      protocols?: string[] | string,
      options?: ClientOptions,
    );

    send(data: RawData, options?: SendOptions): void;
    close(code?: number): void;
    terminate(): void;

    on(event: 'message', listener: (data: RawData, isBinary: boolean) => void): this;
    on(event: 'error', listener: (error: Error) => void): this;
    on(event: 'close', listener: (code: number, reason: Buffer) => void): this;

    once(event: 'open', listener: () => void): this;
    once(event: 'upgrade', listener: (response: IncomingMessage) => void): this;
    once(
      event: 'unexpected-response',
      listener: (request: ClientRequest, response: IncomingMessage) => void,
    ): this;
    once(event: 'error', listener: (error: Error) => void): this;
    once(event: 'close', listener: (code: number, reason: Buffer) => void): this;
  }

  export class WebSocketServer extends EventEmitter {
    constructor(options?: { noServer?: boolean });

    handleUpgrade(
      request: IncomingMessage,
      socket: Duplex,
      head: Buffer,
      callback: (socket: WebSocket, request: IncomingMessage) => void,
    ): void;

    close(callback?: () => void): void;
  }
}
