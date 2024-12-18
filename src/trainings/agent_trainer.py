import json
from json import JSONDecodeError
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from numpy import floating
from tqdm import tqdm
import matplotlib.pyplot as plt

from src.agents.agent import Agent
from src.enviroments.environment import Environment
from src.utils.ini_config_reader import ConfigReader


class AgentTrainer:
    """A training framework for reinforcement learning agents.

    :param agent: The RL agent to train
    :param env: The training environment
    :param config_reader: ConfigReader for the training configuration. See examples for structure to have.

    :ivar agent: The reinforcement learning agent being trained
    :ivar env: The environment the agent interacts with
    :ivar config_data: Dictionary containing the complete configuration data
    :ivar train_episodes: Number of training episodes to run
    :ivar eval_episodes: Number of episodes used for each evaluation
    :ivar eval_frequency: How often to run evaluation (in episodes)
    :ivar max_steps_per_episode: Maximum number of steps allowed per episode
    :ivar save_frequency: How often to save checkpoints (in episodes)
    :ivar save_path: Directory path where checkpoints are saved
    :ivar log_path: Directory path where logs are saved
    :ivar early_stop_patience: Number of evaluations without improvement before early stopping
    :ivar early_stop_min_improvement: Minimum improvement required to reset early stopping counter
    :ivar train_returns: List of returns from training episodes
    :ivar eval_returns: List of average returns from evaluation periods
    :ivar train_steps: Total number of training steps taken

    :raises ValueError: If config file format is not an INI file or if config file format is invalid
    :raises KeyError: If config file is missing required parameters
    :raises FileNotFoundError: If config file does not exist

    Example:
        Create a configuration file (config.ini):

            [episodes]
            train_episodes = 1000
            eval_episodes = 20
            eval_frequency = 10
            max_steps_per_episode = 500

            [checkpoints]
            save_frequency = 100
            save_path = ./checkpoints
            log_path = ./logs

            [early_stopping]
            early_stop_patience = 20
            early_stop_min_improvement = 0.01


        Basic usage:

            # Create environment and agent
            cart_pole_env = CartPoleEnv()
            env = Environment(cart_pole_env)
            agent = DQNAgent(
                state_dim=env.observation_space.shape[0],
                action_dim=env.action_space.n,
                learning_rate=0.001,
                gamma=0.99
            )

            # Initialize config reader with path to config file
            config_reader = INIConfigReader('training_config.ini')

            # Initialize trainer
            trainer = AgentTrainer(
                agent=agent,
                env=env,
                config_reader=config_reader
            )

            # Train the agent
            training_metrics = trainer.train()

            # Evaluate trained agent
            final_performance = trainer.evaluate(num_episodes=100)
            print(f"Final average return: {final_performance}")


        Starting from checkpoint:
        # Initialize components
            cart_pole_env = CartPoleEnv()
            env = Environment(cart_pole_env)
            agent = DQNAgent(
                state_dim=env.observation_space.shape[0],
                action_dim=env.action_space.n,
                learning_rate=0.001,
                gamma=0.99
            )

            # Load agent from checkpoint
            agent_path, env_path, training_state_path = AgentTrainer.get_checkpoint_paths('./checkpoints',10)
            agent.load(agent_path)
            env.load(env_path)
            trainer = AgentTrainer.from_checkpoint(
                agent=agent,
                env=env,
                checkpoint_file=training_state_path
            )

            # Continue training or evaluate
            training_metrics = trainer.train()  # Continue training
            eval_score = trainer.evaluate(num_episodes=50)  # Evaluate performance
            print(f"Evaluation score: {eval_score}")

        Training with live plotting:
            # Setup environment and agent
            cart_pole_env = CartPoleEnv()
            env = Environment(cart_pole_env)
            agent = DQNAgent(
                state_dim=env.observation_space.shape[0],
                action_dim=env.action_space.n,
                learning_rate=0.001,
                gamma=0.99
            )

            # Initialize trainer
            config_reader = ConfigReader('config.ini')
            trainer = AgentTrainer(
                agent=agent,
                env=env,
                config_reader=config_reader
            )

            # Train with live progress plotting
            metrics = trainer.train(plot_progress=True)  # Will show plot during training

            # Plot final results
            trainer.plot_progress()  # Plot using collected metrics

            print("Training metrics:", metrics)
"""

    def __init__(self, agent: Agent, env: Environment, config_reader: ConfigReader):
        self.agent = agent
        self.env = env
        # Load config file
        self._load_config(config_reader)
        # Training metrics
        self.train_returns = []
        self.eval_returns = []
        self.train_steps = 0
        self.episode = 0
        # Plotting
        self._fig = None
        self._ax = None

    def _load_config(self, config_reader: ConfigReader) -> None:
        """Load and validate configuration from an INI file.

        :param config_reader: A ConfigReader object with contains all the configuration of the training.
        :raises ValueError: If config file format is not an INI file or if config file format is invalid
        :raises KeyError: If config file is missing required parameters
        :raises FileNotFoundError: If config file does not exist
        """
        self.config_data = config_reader.config_data
        # Episodes
        self.train_episodes = config_reader.get_param('episodes.train_episodes')
        self.eval_episodes = config_reader.get_param('episodes.eval_episodes')
        self.eval_frequency = config_reader.get_param('episodes.eval_frequency')
        self.max_steps_per_episode = config_reader.get_param('episodes.max_steps_per_episode')
        # Checkpoints
        self.save_frequency = config_reader.get_param('checkpoints.save_frequency')
        self.save_path = config_reader.get_param('checkpoints.save_path')
        self.log_path = config_reader.get_param('checkpoints.log_path')
        # Hyperparameters
        self.early_stop_patience = config_reader.get_param('early_stop_patience')
        self.early_stop_min_improvement = config_reader.get_param('early_stop_patience')

    @staticmethod
    def from_checkpoint(agent: Agent, env: Environment, checkpoint_file: str):
        """
        Creates an AgentTrainer instance from the given checkpoint.
        :param agent: the agent to use for the training. Careful! Load it before starting the training with proper  methods.
        :param env: the environment to use for the training. Careful! Load it before starting the training with proper
            methods.
        :param checkpoint_file: the file that contains the training state.
        :raises FileNotFoundError: if file doesn't exist-
        :raises ValueError: if file is not in the valid format.
        :return: AgentTrainer loaded object.
        """
        with open(checkpoint_file, 'w') as f:
            try:
                checkpoint = json.load(f)
            except JSONDecodeError | TypeError | UnicodeDecodeError as e:
                raise ValueError(f"Invalid file format: \n{e}")

        trainer = AgentTrainer(
            agent,
            env,
            ConfigReader(checkpoint)
        )
        trainer.train_returns = checkpoint['train_returns']
        trainer.eval_returns = checkpoint['eval_returns']
        trainer.train_steps = checkpoint['train_steps']
        trainer.episode = checkpoint['episode']

    def plot_progress(self) -> None:
        """Plot the training and evaluation returns.

        Creates a figure showing the training returns and evaluation returns
        over episodes.
        """
        plt.close('all')  # Close any existing figures
        self._fig, self._ax = plt.subplots(figsize=(10, 5))

        # Plot training returns
        self._ax.plot(self.train_returns, label='Training Returns', alpha=0.6)

        # Plot evaluation returns at correct episodes
        if self.eval_returns:
            eval_episodes = range(0, len(self.eval_returns) * self.eval_frequency,
                                  self.eval_frequency)
            self._ax.plot(eval_episodes, self.eval_returns,
                          label='Evaluation Returns', linewidth=2)

        self._ax.set_xlabel('Episode')
        self._ax.set_ylabel('Return')
        self._ax.legend()
        self._ax.set_title('Training Progress')
        plt.show()

    def _update_plot(self) -> None:
        """Update the live training plot.

        Called during training when plot_progress=True to update the plot
        in real-time.
        """
        if self._fig is None or self._ax is None:
            self.plot_progress()
        else:
            self._ax.clear()
            self._ax.plot(self.train_returns, label='Training Returns', alpha=0.6)

            if self.eval_returns:
                eval_episodes = range(0, len(self.eval_returns) * self.eval_frequency,
                                      self.eval_frequency)
                self._ax.plot(eval_episodes, self.eval_returns,
                              label='Evaluation Returns', linewidth=2)

            self._ax.set_xlabel('Episode')
            self._ax.set_ylabel('Return')
            self._ax.legend()
            self._ax.set_title('Training Progress')
            self._fig.canvas.draw()
            plt.pause(0.01)  # Small pause to update the plot

    def train(self, plot_progress: bool = False, verbosity: str = "INFO") -> Dict[str, list]:
        """Train the agent using the specified configuration.
        Some features:
            - Periodic evaluation
            - Early stopping
            - Tracking of checkpoints
            - Configurable verbosity levels

        :param plot_progress: Whether to show and update a plot during training
        :param verbosity: Print verbosity level ('DEBUG', 'INFO', 'WARNING', 'NONE')
        :return: Dictionary containing training metrics including:
                - 'train_returns': List of returns from training episodes
                - 'eval_returns': List of average returns from evaluation periods
                - 'train_steps': Total number of training steps taken
        """
        # Set verbosity level
        verbosity = verbosity.upper()
        verbosity_levels = {"DEBUG": 3, "INFO": 2, "WARNING": 1, 'NONE': 0}
        verbosity_level = verbosity_levels.get(verbosity, 0)  # Default to NONE

        if verbosity_level >= 2:
            print(f"Starting training with {self.train_episodes} episodes")
        if verbosity_level >= 3:
            print(f"Configuration - Eval frequency: {self.eval_frequency}, "
                  f"Early stop patience: {self.early_stop_patience}, "
                  f"Save frequency: {self.save_frequency}")

        best_eval_return = float('-inf')
        episodes_without_improvement = 0

        for self.episode in tqdm(range(self.train_episodes)):
            # Training episode
            if verbosity_level >= 3:
                print(f"Starting episode {self.episode + 1}/{self.train_episodes}")
            episode_return = self._run_episode(training=True)
            self.train_returns.append(episode_return)
            if verbosity_level >= 3:
                print(f"Episode {self.episode} completed with reward: {episode_return:.2f}")

            # Periodic evaluation
            if self.episode % self.eval_frequency == 0:
                if verbosity_level >= 2:
                    print(f"Running evaluation at episode {self.episode}")
                eval_return = self.evaluate(self.eval_episodes)
                self.eval_returns.append(eval_return)
                if verbosity_level >= 2:
                    print(f"Evaluation return: {eval_return:.2f}")

                # Update plot if requested
                if plot_progress:
                    if verbosity_level >= 3:
                        print("Updating training progress plot")
                    self._update_plot()

                # Early stopping check
                if eval_return > best_eval_return + self.early_stop_min_improvement:
                    best_eval_return = eval_return
                    episodes_without_improvement = 0
                    if verbosity_level >= 2:
                        print(f"New best evaluation return: {best_eval_return:.2f}")
                else:
                    episodes_without_improvement += 1
                    if verbosity_level >= 3:
                        print(f"Episodes without improvement: {episodes_without_improvement}")

                if episodes_without_improvement >= self.early_stop_patience:
                    if verbosity_level >= 1:
                        print(f"Early stopping triggered at episode {self.episode}")
                    break

            # Save checkpoint
            if self.episode % self.save_frequency == 0:
                if verbosity_level >= 2:
                    print(f"Saving checkpoint at episode {self.episode}")
                self._save_checkpoint()

        # Final plot update if plotting was enabled
        if plot_progress:
            if verbosity_level >= 3:
                print("Updating final training progress plot")
            self._update_plot()

        if verbosity_level >= 2:
            print("Training completed")
            print(f"Final training steps: {self.train_steps}")
        if verbosity_level >= 3:
            print(f"Final training returns: {self.train_returns[-1]:.2f}")
            print(f"Final evaluation returns: {self.eval_returns[-1]:.2f}")

        return {
            'train_returns': self.train_returns,
            'eval_returns': self.eval_returns,
            'train_steps': self.train_steps
        }

    def evaluate(self, num_episodes: int, verbosity: str = "INFO") -> floating[Any]:
        """Evaluate the agent's performance by running multiple episodes without training.

        :param num_episodes: Number of evaluation episodes to run
        :param verbosity: Print verbosity level ('DEBUG', 'INFO', 'WARNING', 'NONE')
        :return: Average return across all evaluation episodes
        """
        verbosity_levels = {"DEBUG": 3, "INFO": 2, "WARNING": 1, 'NONE': 0}
        verbosity_level = verbosity_levels.get(verbosity, 0)
        eval_returns = []
        for i in range(num_episodes):
            if verbosity_level >= 3:
                print(f"Starting episode {i + 1}/{num_episodes}")
            episode_return = self._run_episode(training=False)
            if verbosity_level >= 3:
                print(f"Reward of episode {i + 1}: {episode_return}")
            eval_returns.append(episode_return)
        return np.mean(eval_returns)

    def _run_episode(self, training: bool = True) -> float:
        """Run a single episode in the environment.

        :param training: Whether to update the agent during the episode
        :return: Total reward accumulated during the episode
        """
        state, _ = self.env.reset()
        self.agent.reset()
        episode_return = 0

        for step in range(self.max_steps_per_episode):
            # Select action
            action = self.agent.act(state, explore=training)

            # Take step in environment
            next_state, reward, terminated, truncated, _ = self.env.step(action)
            done = terminated or truncated

            # Update agent if training
            if training:
                self.agent.update(state, action, reward, next_state, done)
                self.train_steps += 1

            episode_return += reward
            state = next_state

            if done:
                break

        return episode_return

    def _save_checkpoint(self) -> None:
        """Save the current state of training to disk.
        """
        save_dir = Path(self.save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            'episode': self.episode,
            'train_returns': self.train_returns,
            'eval_returns': self.eval_returns,
            'train_steps': self.train_steps,
            'config': self.config_data
        }

        agent_path, env_path, state_path = AgentTrainer.get_checkpoint_paths(save_dir, self.episode)
        # Save agent
        self.agent.save(str(agent_path))
        # Save environment
        self.env.save(str(env_path))
        # Save training state
        with open(state_path, 'w') as f:
            json.dump(checkpoint, f, indent=4)

    @staticmethod
    def get_checkpoint_paths(save_dir: str | Path, episode: int) -> Tuple[Path, Path, Path]:
        """
        Computes the paths of the agent, environment and training state files for the checkpoint.
        :param save_dir: the directory which contains all the checkpoints.
        :param episode: the episode of the checkpoints.
        :return: (agent_path,env_path,training_state_path)
        """

        save_dir_path = Path(save_dir)
        return (
            save_dir_path / "agents" / f"agent_ep{episode}.pt",
            save_dir_path / "environments" / f"agent_ep{episode}.pt",
            save_dir_path / "trainings" / f"agent_ep{episode}.pt")

