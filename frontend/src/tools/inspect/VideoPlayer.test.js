import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import VideoPlayer from './VideoPlayer.svelte';

describe('Inspect video player', () => {
  it('keeps an unrotated control bar outside the transformed video canvas', () => {
    const { body } = render(VideoPlayer, {
      props: {
        src: '/files/case/media/clip.mp4',
        transform: 'rotate(90deg)',
        quarterTurn: true,
        duration: 125,
        currentTime: 5,
        ontimeupdate: () => {},
      },
    });

    expect(body).toContain('class="video-canvas ');
    expect(body).toContain('style="transform: rotate(90deg);"');
    expect(body).toContain('class="player-bar ');
    expect(body.indexOf('class="player-bar ')).toBeGreaterThan(body.indexOf('</video>'));
    expect(body).toContain('aria-label="Video position"');
    expect(body).toContain('0:05 / 2:05');
    expect(body).not.toContain(' controls');
  });
});
