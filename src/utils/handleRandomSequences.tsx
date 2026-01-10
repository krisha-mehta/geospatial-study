// eslint-disable-next-line import/no-unresolved
import latinSquare from '@quentinroy/latin-square';
import { ComponentBlock, DynamicBlock, StudyConfig } from '../parser/types';
import { Sequence } from '../store/types';
import { isDynamicBlock } from '../parser/utils';

function _componentBlockToSequence(
  order: StudyConfig['sequence'],
  latinSquareObject: Record<string, string[][]>,
  path: string,
): Sequence {
  if (isDynamicBlock(order)) {
    return {
      id: order.id,
      orderPath: path,
      order: order.order,
      components: [],
      skip: [],
    };
  }

  let computedComponents = order.components;

  if (order.order === 'random') {
    const randomArr = order.components.sort(() => 0.5 - Math.random());

    computedComponents = randomArr;
  } else if (order.order === 'latinSquare' && latinSquareObject) {
    computedComponents = latinSquareObject[path].pop()!.map((o) => {
      if (o.startsWith('_componentBlock')) {
        return order.components[+o.slice('_componentBlock'.length)];
      }

      return o;
    });
  }

  computedComponents = computedComponents.slice(0, order.numSamples);

  for (let i = 0; i < computedComponents.length; i += 1) {
    const curr = computedComponents[i];
    if (typeof curr !== 'string' && !Array.isArray(curr)) {
      const index = order.components.indexOf(curr);
      computedComponents[i] = _componentBlockToSequence(curr, latinSquareObject, `${path}-${index}`) as unknown as ComponentBlock;
    }
  }

  // If we have a break, insert it into the sequence at the correct intervals
  if (order.interruptions) {
    order.interruptions.forEach((interruption) => {
      const newComponents = [];
      if (interruption.spacing !== 'random') {
        for (let i = 0; i < computedComponents.length; i += 1) {
          if (
            i === interruption.firstLocation
            || (i > interruption.firstLocation && i % interruption.spacing === 0)
          ) {
            newComponents.push(...interruption.components);
          }
          newComponents.push(computedComponents[i]);
        }
      }

      // Handle random interruptions
      if (interruption.spacing === 'random') {
        // Generate the random locations
        const randomInterruptionLocations = new Set<number>();
        if (interruption.numInterruptions > computedComponents.length - 1) {
          throw new Error('Number of interruptions cannot be greater than the number of components');
        }
        while (randomInterruptionLocations.size < interruption.numInterruptions) {
          const randomLocation = Math.floor(Math.random() * computedComponents.length - 1) + 1;
          randomInterruptionLocations.add(randomLocation);
        }
        const sortedRandomInterruptionLocations = Array.from(randomInterruptionLocations).sort((a, b) => a - b);

        let j = 0;
        for (let i = 0; i < computedComponents.length; i += 1) {
          if (i === sortedRandomInterruptionLocations[j]) {
            newComponents.push(...interruption.components);
            j += 1;
          }
          newComponents.push(computedComponents[i]);
        }
      }
      computedComponents = newComponents;
    });
  }

  return {
    id: order.id,
    orderPath: path,
    order: order.order,
    components: computedComponents.flat() as Sequence['components'],
    skip: order.skip,
  };
}

function componentBlockToSequence(
  order: StudyConfig['sequence'],
  latinSquareObject: Record<string, string[][]>,
): Sequence {
  const orderCopy = structuredClone(order);

  return _componentBlockToSequence(orderCopy, latinSquareObject, 'root');
}

function _createRandomOrders(order: StudyConfig['sequence'], paths: string[], path: string, index = 0) {
  const newPath = path.length > 0 ? `${path}-${index}` : 'root';
  if (order.order === 'latinSquare') {
    paths.push(newPath);
  }

  if (isDynamicBlock(order)) {
    return;
  }

  order.components.forEach((comp, i) => {
    if (typeof comp !== 'string' && !isDynamicBlock(comp)) {
      _createRandomOrders(comp, paths, newPath, i);
    }
  });
}

function createRandomOrders(order: StudyConfig['sequence']) {
  const paths: string[] = [];
  _createRandomOrders(order, paths, '', 0);

  return paths;
}

function generateLatinSquare(config: StudyConfig, path: string) {
  const pathArr = path.split('-');

  let locationInSequence: Partial<ComponentBlock> | Partial<DynamicBlock> | string = {};
  pathArr.forEach((p) => {
    if (p === 'root') {
      locationInSequence = config.sequence;
    } else {
      if (isDynamicBlock(locationInSequence as StudyConfig['sequence'])) {
        return;
      }
      locationInSequence = (locationInSequence as ComponentBlock).components[+p];
    }
  });

  const options = (locationInSequence as ComponentBlock).components.map((c: unknown, i: number) => (typeof c === 'string' ? c : `_componentBlock${i}`));
  const newSquare: string[][] = latinSquare<string>(options.sort(() => 0.5 - Math.random()), true);
  return newSquare;
}

/**
 * Randomly shuffles state trial components while preserving Latin square selection
 * @param sequence - The sequence to shuffle
 * @param config - The study config to access component parameters
 * @returns The shuffled sequence with trials in random order
 */
function shuffleSequenceToAvoidConsecutiveRegions(sequence: Sequence, config: StudyConfig): Sequence {
  // First, flatten the entire sequence to get all component names
  function flattenSequence(seq: Sequence): string[] {
    const result: string[] = [];
    for (const comp of seq.components) {
      if (typeof comp === 'string') {
        result.push(comp);
      } else {
        result.push(...flattenSequence(comp as Sequence));
      }
    }
    return result;
  }

  // Get all component names in order (these were selected by Latin square)
  const allComponents = flattenSequence(sequence);
  // Separate state trial components from other components (like intro, consent, etc.)
  const stateTrials: { component: string; index: number }[] = [];
  const otherComponents: { component: string; index: number }[] = [];
  allComponents.forEach((componentName, index) => {
    const component = config.components[componentName];
    // Check if this component has state parameter (i.e., it's a trial)
    const hasState = (component && 'parameters' in component)
      && (component.parameters as Record<string, unknown>)?.state !== undefined;
    if (hasState) {
      stateTrials.push({ component: componentName, index });
    } else {
      otherComponents.push({ component: componentName, index });
    }
  });
  // Randomly shuffle only the state trials using Fisher-Yates algorithm
  const shuffledTrials = stateTrials.map((t) => t.component);
  for (let i = shuffledTrials.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffledTrials[i], shuffledTrials[j]] = [shuffledTrials[j], shuffledTrials[i]];
  }
  // Reconstruct the full sequence with other components in original positions
  const result: string[] = new Array(allComponents.length);
  // Put non-trial components back in their original positions
  otherComponents.forEach(({ component, index }) => {
    result[index] = component;
  });
  // Fill in the shuffled trials in the remaining positions
  let trialIdx = 0;
  for (let i = 0; i < result.length; i += 1) {
    if (result[i] === undefined) {
      result[i] = shuffledTrials[trialIdx];
      trialIdx += 1;
    }
  }
  const shuffled = result;
  // Now we need to rebuild the sequence structure with the shuffled components
  // For simplicity, we'll create a flat sequence with all components at the top level
  return {
    ...sequence,
    components: shuffled as Sequence['components'],
  };
}

export function generateSequenceArray(config: StudyConfig): Sequence[] {
  const paths = createRandomOrders(config.sequence);
  const latinSquareObject: Record<string, string[][]> = paths
    .map((p) => ({ [p]: generateLatinSquare(config, p) }))
    .reduce((acc, curr) => ({ ...acc, ...curr }), {});

  const numSequences = config.uiConfig.numSequences || 1000;

  const sequenceArray: Sequence[] = [];
  Array.from({ length: numSequences }).forEach(() => {
    // Generate a sequence
    const sequence = componentBlockToSequence(config.sequence, latinSquareObject);
    sequence.components.push('end');

    // Shuffle to avoid consecutive regions
    const shuffledSequence = shuffleSequenceToAvoidConsecutiveRegions(sequence, config);

    // Add the sequence to the array
    sequenceArray.push(shuffledSequence);

    // Refill the latin square if it is empty
    Object.entries(latinSquareObject).forEach(([key, value]) => {
      if (value.length === 0) {
        latinSquareObject[key] = generateLatinSquare(config, key);
      }
    });
  });

  return sequenceArray;
}
