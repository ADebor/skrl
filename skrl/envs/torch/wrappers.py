from typing import Tuple, Any

import gym
import collections
import numpy as np

import torch

__all__ = ["wrap_env"]

ISSUES = "https://github.com/Toni-SM/skrl/issues"


class Wrapper(object):
    def __init__(self, env: Any) -> None:
        """Base wrapper class for RL environments

        :param env: The environment to wrap
        :type env: Any supported RL environment
        """
        self._env = env

        # device (faster than @property)
        if hasattr(self._env, "device"):
            self.device = torch.device(self._env.device)
        else:
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    def reset(self) -> torch.Tensor:
        """Reset the environment

        :raises NotImplementedError: Not implemented

        :return: The state of the environment
        :rtype: torch.Tensor
        """
        raise NotImplementedError

    def step(self, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Any]:
        """Perform a step in the environment

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :raises NotImplementedError: Not implemented

        :return: The state, the reward, the done flag, and the info
        :rtype: tuple of torch.Tensor and any other info
        """
        raise NotImplementedError

    def render(self, *args, **kwargs) -> None:
        """Render the environment

        :raises NotImplementedError: Not implemented
        """
        raise NotImplementedError

    @property
    def num_envs(self) -> int:
        """Number of environments

        If the wrapped environment does not have the ``num_envs`` property, this property will be set to 1
        """
        return self._env.num_envs if hasattr(self._env, "num_envs") else 1

    @property
    def state_space(self) -> gym.Space:
        """State space

        If the wrapped environment does not have the ``state_space`` property, 
        the value of the ``observation_space`` property will be used
        """
        return self._env.state_space if hasattr(self._env, "state_space") else self._env.observation_space

    @property
    def observation_space(self) -> gym.Space:
        """Observation space
        """
        return self._env.observation_space

    @property
    def action_space(self) -> gym.Space:
        """Action space
        """
        return self._env.action_space


class IsaacGymPreview2Wrapper(Wrapper):
    def __init__(self, env: Any) -> None:
        """Isaac Gym environment (preview 2) wrapper

        :param env: The environment to wrap
        :type env: Any supported Isaac Gym environment (preview 2) environment
        """
        super().__init__(env)
        
        self._reset_once = True
        self._obs_buf = None

    def step(self, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Any]:
        """Perform a step in the environment

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :return: The state, the reward, the done flag, and the info
        :rtype: tuple of torch.Tensor and any other info
        """
        self._obs_buf, rew_buf, reset_buf, info = self._env.step(actions)
        return self._obs_buf, rew_buf.view(-1, 1), reset_buf.view(-1, 1), info

    def reset(self) -> torch.Tensor:
        """Reset the environment

        :return: The state of the environment
        :rtype: torch.Tensor
        """
        if self._reset_once:
            self._obs_buf = self._env.reset()
            self._reset_once = False
        return self._obs_buf

    def render(self, *args, **kwargs) -> None:
        """Render the environment
        """
        pass


class IsaacGymPreview3Wrapper(Wrapper):
    def __init__(self, env: Any) -> None:
        """Isaac Gym environment (preview 3) wrapper

        :param env: The environment to wrap
        :type env: Any supported Isaac Gym environment (preview 3) environment
        """
        super().__init__(env)

        self._reset_once = True
        self._obs_dict = None

    def step(self, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Any]:
        """Perform a step in the environment

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :return: The state, the reward, the done flag, and the info
        :rtype: tuple of torch.Tensor and any other info
        """
        self._obs_dict, rew_buf, reset_buf, info = self._env.step(actions)
        return self._obs_dict["obs"], rew_buf.view(-1, 1), reset_buf.view(-1, 1), info

    def reset(self) -> torch.Tensor:
        """Reset the environment

        :return: The state of the environment
        :rtype: torch.Tensor
        """
        if self._reset_once:
            self._obs_dict = self._env.reset()
            self._reset_once = False
        return self._obs_dict["obs"]

    def render(self, *args, **kwargs) -> None:
        """Render the environment
        """
        pass
    

class GymWrapper(Wrapper):
    def __init__(self, env: Any) -> None:
        """OpenAI Gym environment wrapper

        :param env: The environment to wrap
        :type env: Any supported OpenAI Gym environment
        """
        super().__init__(env)

    def _convert_action(self, actions: torch.Tensor) -> Any:
        """Convert the action to the OpenAI Gym format

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :return: The action in the OpenAI Gym format
        :rtype: Any
        """
        if isinstance(self._env.action_space, gym.spaces.Box):
            if actions.shape[0] == 1:
                return actions.view(-1).cpu().numpy()
            return actions.cpu().numpy()
        elif isinstance(self._env.action_space, gym.spaces.Discrete):
            return actions.item()
        else:
            raise NotImplementedError("Action space type {} not supported".format(type(self._env.action_space)))

    def step(self, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Any]:
        """Perform a step in the environment

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :return: The state, the reward, the done flag, and the info
        :rtype: tuple of torch.Tensor and any other info
        """
        observation, reward, done, info = self._env.step(self._convert_action(actions))
        # convert response to torch
        return torch.tensor(observation, device=self.device).view(1, -1), \
               torch.tensor(reward, device=self.device, dtype=torch.float32).view(1, -1), \
               torch.tensor(done, device=self.device, dtype=torch.bool).view(1, -1), \
               info
        
    def reset(self) -> torch.Tensor:
        """Reset the environment

        :return: The state of the environment
        :rtype: torch.Tensor
        """
        state = self._env.reset()
        if isinstance(state, np.ndarray):
            return torch.tensor(state, device=self.device, dtype=torch.float32).view(1, -1)
        elif isinstance(state, int):
            return torch.tensor(state, device=self.device, dtype=torch.int64).view(1, -1)
        return state.to(self.device).view(1, -1)

    def render(self, *args, **kwargs) -> None:
        """Render the environment
        """
        self._env.render(*args, **kwargs)


class DeepMindWrapper(Wrapper):
    def __init__(self, env: Any) -> None:
        """DeepMind environment wrapper

        :param env: The environment to wrap
        :type env: Any supported DeepMind environment
        """
        super().__init__(env)

        from dm_env import specs
        self._specs = specs

        # observation and action spaces
        self._observation_space = self._spec_to_space(self._env.observation_spec())
        self._action_space = self._spec_to_space(self._env.action_spec())

    @property
    def state_space(self) -> gym.Space:
        """State space

        An alias for the ``observation_space`` property
        """
        return self._observation_space

    @property
    def observation_space(self) -> gym.Space:
        """Observation space
        """
        return self._observation_space

    @property
    def action_space(self) -> gym.Space:
        """Action space
        """
        return self._action_space

    def _spec_to_space(self, spec: Any) -> gym.Space:
        """Convert the DeepMind spec to a Gym space

        :param spec: The DeepMind spec to convert
        :type spec: Any supported DeepMind spec

        :raises: ValueError if the spec type is not supported

        :return: The Gym space
        :rtype: gym.Space
        """
        if isinstance(spec, self._specs.DiscreteArray):
            return gym.spaces.Discrete(spec.num_values)
        elif isinstance(spec, self._specs.BoundedArray):
            return gym.spaces.Box(shape=spec.shape,
                                  low=spec.minimum,
                                  high=spec.maximum,
                                  dtype=spec.dtype)
        elif isinstance(spec, self._specs.Array):
            return gym.spaces.Box(shape=spec.shape,
                                  low=float("-inf"),
                                  high=float("inf"),
                                  dtype=spec.dtype)
        elif isinstance(spec, collections.OrderedDict):
            return gym.spaces.Dict({k: self._spec_to_space(v) for k, v in spec.items()})
        else:
            raise ValueError("Spec type {} not supported. Please report this issue ({})" \
                .format(type(spec), ISSUES))

    def observation_to_tensor(self, observation: Any, spec: Any = None) -> torch.Tensor:
        """Convert the observation to a flat tensor

        :param observation: The observation to convert
        :type observation: Any

        :raises: ValueError if the observation spec type is not supported

        :return: The observation as a flat tensor
        :rtype: torch.Tensor
        """
        spec = spec if spec is not None else self._env.observation_spec()

        if isinstance(spec, self._specs.DiscreteArray):
            return torch.tensor(observation, device=self.device).view(self.num_envs, -1)
        elif isinstance(spec, self._specs.Array):  # includes BoundedArray
            return torch.tensor(observation, device=self.device).view(self.num_envs, -1)
        elif isinstance(spec, collections.OrderedDict):
            keys = sorted(spec.keys())
            return torch.cat([self.observation_to_tensor(observation[k], spec[k]) for k in keys], dim=-1).view(self.num_envs, -1)
        else:
            raise ValueError("Observation spec type {} not supported. Please report this issue ({})" \
                .format(type(observation), ISSUES))

    def tensor_to_action(self, actions: torch.Tensor) -> Any:
        """Convert the action to the DeepMind expected format

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :raise ValueError: If the action space type is not supported

        :return: The action in the DeepMind expected format
        :rtype: Any
        """
        spec = self._env.action_spec()

        if isinstance(spec, self._specs.DiscreteArray):
            return np.array(actions.item(), dtype=spec.dtype)
        elif isinstance(spec, self._specs.Array):  # includes BoundedArray
            return np.array(actions.cpu().numpy(), dtype=spec.dtype).reshape(spec.shape)
        else:
            raise ValueError("Action spec type {} not supported. Please report this issue ({})" \
                .format(type(spec), ISSUES))

    def step(self, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Any]:
        """Perform a step in the environment

        :param actions: The actions to perform
        :type actions: torch.Tensor

        :return: The state, the reward, the done flag, and the info
        :rtype: tuple of torch.Tensor and any other info
        """
        timestep = self._env.step(self.tensor_to_action(actions))

        observation = timestep.observation
        reward = timestep.reward
        done = timestep.last()
        info = {}
        
        # convert response to torch
        return self.observation_to_tensor(observation), \
               torch.tensor(reward, device=self.device, dtype=torch.float32).view(self.num_envs, -1), \
               torch.tensor(done, device=self.device, dtype=torch.bool).view(self.num_envs, -1), \
               info


def wrap_env(env, wrapper="auto") -> Wrapper:
    """Wrap an environment to use a common interface

    :param env: The type of wrapper to use (default: "auto").
                If ``auto``, the wrapper will be automatically selected based on the environment class.
                The specific wrappers supported are ``gym``, ``dm``, ``isaacgym-preview2`` and ``isaacgym-preview3``
    :type env: gym.Env, rlgpu.tasks.base.vec_task.VecTask or isaacgymenvs.tasks.base.vec_task.VecTask
    :param wrapper: The environment to be wrapped
    :type wrapper: str, optional
    
    :raises ValueError: Unknow wrapper type
    
    :return: Wrapped environment
    :rtype: Wrapper
    """
    print("[INFO] Environment:", [str(base).replace("<class '", "").replace("'>", "") \
        for base in env.__class__.__bases__])
    
    if wrapper == "auto":
        if isinstance(env, gym.core.Env) or isinstance(env, gym.core.Wrapper):
            print("[INFO] Wrapper: Gym")
            return GymWrapper(env)
        elif "<class 'dm_env._environment.Environment'>" in [str(base) for base in env.__class__.__bases__]:
            print("[INFO] Wrapper: DeepMind")
            return DeepMindWrapper(env)
        elif "<class 'rlgpu.tasks.base.vec_task.VecTask'>" in [str(base) for base in env.__class__.__bases__]:
            print("[INFO] Wrapper: Isaac Gym (preview 2)")
            return IsaacGymPreview2Wrapper(env)
        print("[INFO] Wrapper: Isaac Gym (preview 3)")
        return IsaacGymPreview3Wrapper(env)
    elif wrapper == "gym":
        print("[INFO] Wrapper: Gym")
        return GymWrapper(env)
    elif wrapper == "dm":
        print("[INFO] Wrapper: DeepMind")
        return DeepMindWrapper(env)
    elif wrapper == "isaacgym-preview2":
        print("[INFO] Wrapper: Isaac Gym (preview 2)")
        return IsaacGymPreview2Wrapper(env)
    elif wrapper == "isaacgym-preview3":
        print("[INFO] Wrapper: Isaac Gym (preview 3)")
        return IsaacGymPreview3Wrapper(env)
    else:
        raise ValueError("Unknown {} wrapper type".format(wrapper))
