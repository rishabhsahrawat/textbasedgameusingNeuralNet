import keras
from keras.models import Sequential, Model
from keras.layers import LSTM, Dense, Embedding, Merge, MaxPool3D
from keras import losses
import random
import numpy as np
from collections import deque
from .base import Model
from games import game
from games.game import *

#-----------LSTM Neural Network-------
class LSTMNOBJ(Model):
    def __init__(self,game, rnn_size=100, batch_size=25,
               seq_length=30, embed_dim=100, layer_depth=3,
               start_epsilon=1, epsilon_end_time=1000000,
               memory_size=1000000,
               checkpoint_dir="checkpoint", forward_only=False):
        self.epsilon = self.start_epsilon = 1.0
        self.final_epsilon = 0.05
        self.observe = 50000
        self.gamma = 0.99
        self.batch_size = 20
        self.game = game
        self.dataset = game.name
        self.aCT = self.game.actions
        self.action_lstm()
        self.abcd()
#----lstm for scoring actions----
    def action_lstm(self):
        actionscorer_lstm = Sequential()
        actionscorer_lstm.add(Embedding(input_dim=100, output_dim=100, input_length=30))
        actionscorer_lstm.add(LSTM(units=64,activation='relu'))
        actionscorer_lstm.add(Dense(units=5))
        return actionscorer_lstm
#------lstm with two inputs using Keras Merge Layer----
    def abcd(self):
        state_model = Sequential()
        state_model.add(Embedding(input_dim=100, output_dim=100, input_length=30))
        state_model.add(LSTM(100, return_sequences=True,activation='relu'))

        actionscorer = Sequential()
        actionscorer.add(Embedding(input_dim=100, output_dim=100, input_length=30))
        actionscorer.add(LSTM(100, return_sequences=True,activation='relu'))

        actionscorer.add(Dense(units=5))

        final_model = Sequential()
        final_model.add(Merge([state_model, actionscorer], mode='concat'))
        final_model.add(Dense(units=8))
        final_model.compile(optimizer='adam', loss='mse')
        #final_model.compile(optimizer=keras.optimizers.SGD(lr=0.01), loss='binary_crossentropy')
        return final_model


    def train(self):
        num_action = len(self.game.actions)
        num_object = len(self.game.objects)

        memory = deque()
        state_t, reward, is_finished = self.game.new_game()
        action_t = np.zeros([num_action])
        object_t = np.zeros([num_object])
        t = 0
        loss = 0
        loss_object = 0
        win_count = 0

        while (True): #OR we can also put a condition  for t in range(0, 1000)
            #Ist predictions
            state_t = np.array(state_t)
            state_t = state_t.reshape(1, state_t.shape[0])

            all_actions = self.action_lstm().predict(state_t)
            all_objects = self.abcd().predict([state_t, state_t])

            #epsilon for chossing actions randomly or with high probability
            if random.random() <= self.epsilon or t <= self.observe:
                action_index = random.randrange(0, num_action-1)
                object_index = random.randrange(0, num_object-1)
            else:
                max_actionelement = np.amax(all_actions[0])#finding the max value object
                action_index = np.where(all_actions[0] == max_actionelement)[0]#index of the max object
                action_index = action_index[0]

                max_element = np.amax(all_objects[0])#finding the max value action
                object_index = np.where(all_objects[0] == max_element)[0]#index of the max action value
                object_index = object_index[0]

            state_next, reward_next, is_finished = self.game.do(action_index, object_index)

            memory.append((state_t, reward_next, action_index, object_index,state_next, is_finished)) #QUEUE
            self.epsilon -= (self.start_epsilon-self.final_epsilon)/self.observe

#-----------training of the Neural Net------
            if t>self.observe:
                batch = random.sample(memory, self.batch_size)
                #for storing game states
                inputs = np.zeros((self.batch_size, state_t.shape[1]))
                #for storing the scores
                target_actions = np.zeros((inputs.shape[0], num_action))
                target_objects = np.zeros((inputs.shape[0], num_object))

                for i in range(0, len(batch)):#batch len 25
                    state_c = batch[i][0]
                    reward_c = batch[i][1]
                    action_c = batch[i][2]
                    object_c = batch[i][3]
                    state_n = batch[i][4]
                    is_finished = batch[i][5]

                    if reward_c > 0:
                        win_count += 1

                    inputs[i:i+1] = state_c
                    target_actions[i] = self.action_lstm().predict(state_c)
                    target_objects[i] = self.abcd().predict([state_c, state_c])
                    print "..."
                    state_n = np.array(state_n)
                    state_n = state_n.reshape(1, state_n.shape[0])
                    Q_value_action = self.action_lstm().predict(state_n)
                    Q_Value_object = self.abcd().predict([state_n, state_n])
                    max_Qact = np.max(Q_value_action)
                    max_Qobj = np.max(Q_Value_object)
                    Q_avg = (max_Qact + max_Qobj)/2 #Q_value taken as the average of action and object

                    if is_finished:
                        target_objects[i, object_index] = reward_c
                    else:
                        target_objects[i, object_c] = reward_c + self.gamma * Q_avg
                     
                loss_object += self.abcd().train_on_batch(x = [inputs, inputs], y = target_objects)


                print "wins ", win_count
                print "loss ", loss_object
                print "Q_avg", Q_avg
                print "----------------------------"
            if t<self.observe:
                print "Observing......"
            if t>self.observe:
                print "Training..."
            print "count ", t

            print "\n"
            t += 1
            state_t = state_next
            if is_finished:
                state_t, reward, is_finished = game.new_game()
