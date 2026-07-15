import { describe, it, expect } from 'vitest';
import { overlayHost, portal } from './fullscreen.js';

// Minimal DOM stand-ins: the action only ever appends and removes, so a couple
// of objects tracking parentage are enough (no jsdom in this suite).
function makeNode() {
  const node = {
    parent: null,
    remove() {
      if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this);
      this.parent = null;
    },
  };
  return node;
}

function makeHost(name) {
  return {
    name,
    children: [],
    appendChild(node) {
      node.remove();
      node.parent = this;
      this.children.push(node);
    },
  };
}

function makeDoc(body) {
  return {
    body,
    fullscreenElement: null,
    listeners: [],
    addEventListener(type, fn) {
      if (type === 'fullscreenchange') this.listeners.push(fn);
    },
    removeEventListener(type, fn) {
      this.listeners = this.listeners.filter((l) => l !== fn);
    },
    fire() {
      for (const l of [...this.listeners]) l();
    },
  };
}

describe('overlayHost', () => {
  it('is the body when nothing is fullscreen', () => {
    const body = makeHost('body');
    expect(overlayHost(makeDoc(body))).toBe(body);
  });

  it('is the fullscreen element while a tool owns the screen', () => {
    const body = makeHost('body');
    const tool = makeHost('tool');
    const doc = makeDoc(body);
    doc.fullscreenElement = tool;
    expect(overlayHost(doc)).toBe(tool);
  });
});

describe('portal', () => {
  it('parks the overlay on the body outside fullscreen', () => {
    const body = makeHost('body');
    const doc = makeDoc(body);
    const node = makeNode();

    portal(node, doc);

    expect(node.parent).toBe(body);
  });

  it('moves the overlay into the fullscreen element on entering', () => {
    const body = makeHost('body');
    const tool = makeHost('tool');
    const doc = makeDoc(body);
    const node = makeNode();

    portal(node, doc);
    doc.fullscreenElement = tool;
    doc.fire();

    // this is the bug: an overlay left on <body> is never painted in fullscreen
    expect(node.parent).toBe(tool);
    expect(body.children).toEqual([]);
  });

  it('moves the overlay back to the body on exiting', () => {
    const body = makeHost('body');
    const tool = makeHost('tool');
    const doc = makeDoc(body);
    const node = makeNode();

    doc.fullscreenElement = tool;
    portal(node, doc);
    doc.fullscreenElement = null;
    doc.fire();

    expect(node.parent).toBe(body);
    expect(tool.children).toEqual([]);
  });

  it('opens directly inside the fullscreen element when already fullscreen', () => {
    const body = makeHost('body');
    const tool = makeHost('tool');
    const doc = makeDoc(body);
    doc.fullscreenElement = tool;
    const node = makeNode();

    portal(node, doc);

    expect(node.parent).toBe(tool);
  });

  it('does not re-append when the host is unchanged', () => {
    const body = makeHost('body');
    const doc = makeDoc(body);
    const node = makeNode();

    portal(node, doc);
    doc.fire();
    doc.fire();

    expect(body.children).toEqual([node]);
  });

  it('unhooks and detaches on destroy', () => {
    const body = makeHost('body');
    const doc = makeDoc(body);
    const node = makeNode();

    portal(node, doc).destroy();

    expect(doc.listeners).toEqual([]);
    expect(body.children).toEqual([]);
    expect(node.parent).toBe(null);
  });
});
